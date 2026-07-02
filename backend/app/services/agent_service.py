"""LangGraph ReAct Agent — Plan-Act-Observe loop.

Architecture:
    START → plan_node (LLM generates execution plan)
          → act_node (LLM with tools, executes next step)
          → tools (local execution)
          → observe_node (evaluate result, update plan)
            ├→ act_node (more steps remain)
            └→ END (plan complete)

This is a REAL ReAct agent with explicit planning, not a hardcoded DAG.
"""

from typing import Annotated, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

from app.infrastructure.llm_client import get_model
from app.services.tools import get_all_tools, set_tool_context
from app.services.session_agent import SessionAgentManager
from app.services.invoice_card_service import build_invoice_card
from app.services.policy_card_service import build_policy_card, build_policy_card_out_of_scope
from app.config import settings

# ============================================================
# Agent tools
# ============================================================

AGENT_TOOLS = get_all_tools()

# ============================================================
# System Prompt
# ============================================================

SYSTEM_PROMPT = """你是公司内部的报销助手 AI Agent。你的名字叫"小报"。

你拥有以下工具能力:
1. **scan_invoice** — 扫描发票/收据，提取金额、类别、日期、商家
2. **search_knowledge** — 搜索公司报销政策和标准
3. **check_reimbursement_status** — 查询报销单审批进度
4. **submit_reimbursement** — 向公司内部系统提交报销申请
5. **send_notification** — 发送邮件通知员工报销进展

## 工作流程

当收到报销请求时，按以下原则自主决策:
1. **先扫描**: 有发票文件时，先调 scan_invoice 提取信息
2. **再查政策**: 根据发票类别，调 search_knowledge 查询对应报销标准
3. **比对待遇**: 对比发票金额和公司政策，做出判断
4. **确认用户**: 在提交前，必须先向用户确认报销金额和类别
5. **提交执行**: 用户确认后，调 submit_reimbursement 提交
6. **通知结果**: 提交完成后，调 send_notification 通知用户

## 意图识别

用户消息可能是报销请求，也可能是政策咨询。你需要智能判断意图，不要追问：
- 用户提到「餐补」「住宿标准」「差旅标准」「什么可以报」「能报吗」等 → 理解为**政策咨询**
  → 调用 search_knowledge 查询，然后用自然语言总结政策要点
  → **不要**问「您是想咨询政策还是想报销？」
  → **不要**要求用户上传发票
- 用户上传了发票文件 + 提到「报销」→ 理解为**报销请求**
  → 走 scan_invoice → search_knowledge → 确认 → 提交流程
- 用户直接说「帮我报销」但没有上传 → 告知需要上传发票

## 决策原则

- 金额在标准范围内 → 可报销，向用户确认后提交
- 金额超出标准 → 解释原因，告知用户哪些部分可报哪些不可报，询问是否仍要提交
- 信息不足 → 向用户追问（不要编造信息）
- 无法判断 → 告知用户原因，建议人工处理
- 每次判断必须引用具体的政策条款

## 严格规则

- 不要编造政策规则 — 只依据 search_knowledge 返回的内容
- 报销金额不能超过发票金额
- 提交前必须获得用户确认
- 你是决策和执行引擎 — 可以改变系统状态，不只是回答问题
- 所有操作都有审计日志，请认真对待每笔报销
- 当 search_knowledge 返回结果且用户没有上传发票时，你必须用自然语言总结政策内容。
  不要只说「请查看卡片」，而要在文字回复中引用具体的政策条款和金额上限。
  文字总结应包含：适用范围、金额标准、报销比例、上限、特殊条件。

## 纯闲聊/非报销问题
如果用户不是问报销相关问题，直接用中文友好回复，不需要调用工具。
"""


# ============================================================
# Agent State
# ============================================================

class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    plan: list[dict]         # [{step, tool, args, status: pending|running|done|failed}]
    current_step: int
    iteration_count: int
    plan_complete: bool      # observe_node sets this
    session_id: str          # for session-scoped model lookup


# ============================================================
# Plan Node — LLM generates execution plan
# ============================================================

PLAN_PROMPT = """你是一个报销审批系统的任务编排器。根据用户的请求，生成一个简洁的执行计划。

可用工具列表:
- scan_invoice — OCR 扫描发票，提取金额、商户、日期、品类。**只有用户上传了发票文件才能调用此工具！**
- search_knowledge — 搜索公司报销政策知识库
- check_reimbursement_status — 查询报销单审批进度
- submit_reimbursement — 提交报销申请到内部系统
- send_notification — 发送邮件通知

**关键规则：**
1. 用户必须有发票文件才能调用 scan_invoice。用户消息包含 "[已上传文件:" 或 "[Uploaded:" 表示已有发票文件。
2. 如果用户没说上传也没提到文件，就生成 search_knowledge 计划，不要包含 scan_invoice。
3. submit_reimbursement 和 send_notification **绝对不能在 plan 中出现**——它们由后续确认步骤触发，不是初始计划的一部分。
4. 用户问政策/标准/类型/条件 → search_knowledge
5. 用户打招呼/闲聊/自我介绍 → []
6. 用户说"报销"但没有发票文件 → 直接回复请用户上传，plan 返回 []
7. 用户问「餐补」「住宿标准」「差旅标准」等政策咨询类关键词 → 生成 search_knowledge 计划，不要返回空计划

请直接输出一个 JSON 数组，不要输出其他任何内容:
[{"step": "步骤描述", "tool": "工具名", "args": {"参数名": "参数值"}}]

示例:
- 用户消息"[已上传文件: receipt.png] 帮我报销": [{"step": "扫描发票", "tool": "scan_invoice", "args": {"file_path": "receipt.png"}}, {"step": "查询报销政策", "tool": "search_knowledge", "args": {"query": "餐饮报销标准"}}]
- 用户问"什么类型可以报销": [{"step": "搜索报销规则", "tool": "search_knowledge", "args": {"query": "报销类型 报销条件"}}]
- 用户问"餐补标准": [{"step": "搜索餐补政策", "tool": "search_knowledge", "args": {"query": "餐补标准"}}]
- 用户问"帮我报销"但没有发票文件: []
- 用户打招呼: []

JSON 数组:"""


def plan_node(state: AgentState) -> dict:
    """Generate an execution plan using the LLM (or mock)."""
    session_id = state.get("session_id", "")
    sa = SessionAgentManager.get_or_create(session_id) if session_id else None
    model = sa.get_model() if sa else get_model()
    messages = [SystemMessage(content=PLAN_PROMPT)]
    # Only include the LAST human message — NOT the full conversation history.
    # Full history confuses the plan stage with old tool calls.
    last_human = None
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            last_human = m
            break
    if last_human:
        messages.append(last_human)

    response = model.invoke(messages)
    plan = _parse_plan(response.content)
    return {
        "messages": [response],
        "plan": plan,
        "current_step": 0,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def _parse_plan(content: str) -> list[dict]:
    """Parse plan JSON from LLM response. Returns empty list on failure."""
    import json as _json
    import re
    # Extract JSON array from content (may have markdown fences)
    content = content.strip()
    # Remove markdown code fences
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    try:
        plan = _json.loads(content)
        if isinstance(plan, list):
            for s in plan:
                s.setdefault("status", "pending")
            return plan
    except (_json.JSONDecodeError, TypeError):
        pass
    return []


# ============================================================
# Act Node — LLM decides which tool to call
# ============================================================

def act_node(state: AgentState) -> dict:
    """Call the LLM with tools + plan context."""
    session_id = state.get("session_id", "")
    sa = SessionAgentManager.get_or_create(session_id) if session_id else None
    model = sa.get_model() if sa else get_model()
    model_with_tools = model.bind_tools(AGENT_TOOLS)

    messages = list(state["messages"])
    # Remove plan_node's raw JSON output from conversation ONLY when it's a
    # plain-text AIMessage (no tool_calls) that looks like a JSON array.
    # DeepSeek may return null content + tool_calls together, so guard content.
    messages = [m for m in messages if not (
        isinstance(m, AIMessage)
        and not getattr(m, "tool_calls", None)
        and str(m.content or "").strip().startswith("[{")
    )]

    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    # Inject plan context into the SystemMessage (never Touch HumanMessage or ToolMessage)
    plan = state.get("plan", [])
    if plan:
        step = state.get("current_step", 0)
        pending = [s for s in plan if s["status"] == "pending"]
        plan_hint = (
            f"\n\n[执行计划] 共 {len(plan)} 步, 当前执行第 {step + 1} 步。"
            f"待执行: {[p['step'] for p in pending]}"
        )
        for i, m in enumerate(messages):
            if isinstance(m, SystemMessage):
                messages[i] = SystemMessage(content=str(m.content) + plan_hint)
                break

    response = model_with_tools.invoke(messages)
    iteration = state.get("iteration_count", 0) + 1
    return {
        "messages": [response],
        "iteration_count": iteration,
    }


def _looks_like_plan(content: str) -> bool:
    """Check if a message looks like a JSON plan (to filter from conversation)."""
    c = content.strip()
    return bool(c.startswith("[{") or c.startswith("```json") or c.startswith("```"))


# ============================================================
# Observe Node — evaluate tool result, update plan
# ============================================================

def observe_node(state: AgentState) -> dict:
    """Check the tool result, mark step as done, decide next action."""
    plan = list(state.get("plan", []))
    current_step = state.get("current_step", 0)
    iteration = state.get("iteration_count", 0) + 1

    last_message = state["messages"][-1]
    result_ok = True
    if isinstance(last_message, ToolMessage):
        result_ok = "error" not in str(last_message.content).lower()

    # Mark current pending step as done/failed
    for s in plan:
        if s["status"] == "pending":
            s["status"] = "done" if result_ok else "failed"
            break

    current_step += 1
    plan_complete = current_step >= len(plan) or not any(
        s["status"] == "pending" for s in plan
    )

    return {
        "plan": plan,
        "current_step": current_step,
        "iteration_count": iteration,
        "plan_complete": plan_complete,  # type: ignore
    }


# ============================================================
# Tool Node
# ============================================================

tool_node = ToolNode(AGENT_TOOLS)


# ============================================================
# Routers
# ============================================================

def after_plan(state: AgentState) -> Literal["act", "__end__"]:
    """After planning: always go to act. act_node handles both empty plan (casual chat) and planned execution."""
    return "act"


def after_act(state: AgentState) -> Literal["tools", "__end__"]:
    """After act: route to tools if LLM called one, else end."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


def after_observe(state: AgentState) -> Literal["act", "__end__"]:
    """After observe: always route back to act so the LLM can process tool results.

    The ReAct loop ends ONLY via after_act (when the LLM produces no tool_calls).
    The plan is a guide, not a hard execution boundary — the LLM must always have
    a chance to synthesize tool results into a user-facing response.
    """
    iteration = state.get("iteration_count", 0)
    if iteration >= 20:
        return "__end__"
    return "act"


# ============================================================
# Build the Graph
# ============================================================

def build_agent_graph() -> StateGraph:
    """Build the PAO agent graph: plan → act ↔ tools → observe → (act | end)."""
    workflow = StateGraph(AgentState)

    workflow.add_node("plan", plan_node)
    workflow.add_node("act", act_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("observe", observe_node)

    workflow.add_edge(START, "plan")
    workflow.add_conditional_edges("plan", after_plan, {"act": "act", "__end__": END})
    workflow.add_conditional_edges("act", after_act, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "observe")
    workflow.add_conditional_edges("observe", after_observe, {"act": "act", "__end__": END})

    return workflow.compile()


# ============================================================
# Singleton
# ============================================================

_agent_graph = None


def get_agent():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph


# ============================================================
# Run Agent (called from Chat API)
# ============================================================

async def run_agent(
    session_id: str,
    user_message: str,
    user_id: int,
    employee_id: int | None,
    user_email: str | None,
    message_history: list[dict] | None = None,
    security_gateway: object | None = None,
    policy_engine: object | None = None,
    calculator_engine: object | None = None,
    rule_engine: object | None = None,
) -> list[dict]:
    """Run the PAO agent and return SSE events.

    Events: plan, thinking, tool_call, tool_result, plan_step_update, message,
            done, supplement_form
    """
    set_tool_context(user_id=user_id, employee_id=employee_id, user_email=user_email,
                     security_gateway=security_gateway, rule_engine=rule_engine)

    agent = get_agent()
    input_messages: list = []

    if message_history:
        for m in message_history:
            if m["role"] == "user":
                input_messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                input_messages.append(AIMessage(content=m["content"] or ""))

    input_messages.append(HumanMessage(content=user_message))

    events: list[dict] = []
    config = {"configurable": {"thread_id": session_id}}
    content_acc = ""
    plan_emitted = False
    plan_buffer = ""  # Buffer plan-node tokens so they never leak to the UI
    last_invoice_result: dict | None = None  # Track scan_invoice result for card generation
    last_search_result: dict | None = None   # Track search_knowledge result for card generation

    async for event in agent.astream_events(
        {"messages": input_messages, "session_id": session_id},
        config=config,
        version="v2",
    ):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            token = str(chunk.content) if chunk.content else ""
            if token:
                if not plan_emitted:
                    # Buffer plan-node tokens silently — never leak JSON to the UI.
                    # Single '[', ']', '[{', '[]' tokens are all part of the plan JSON
                    # and would show as garbage in the chat bubble if streamed.
                    plan_buffer += token
                    continue
                content_acc += token
                events.append({"type": "thinking", "content": token})

        elif kind == "on_chat_model_end":
            output = event["data"]["output"]
            tool_calls = getattr(output, "tool_calls", None) or []

            # Check if this is plan output (from plan_node)
            if not plan_emitted and not tool_calls:
                raw = str(output.content).strip()
                # Any output starting with '[' or '```' from plan_node is a JSON plan.
                # Handle both [{...}] (steps) and [] (empty plan — casual chat).
                if raw.startswith("[") or raw.startswith("```"):
                    plan = _parse_plan(str(output.content))
                    events.append({"type": "plan", "steps": plan})
                    plan_emitted = True
                    plan_buffer = ""  # discard — it was plan JSON
                    content_acc = ""
                    continue
                else:
                    # plan_node returned non-JSON content (rare); flush buffer
                    if plan_buffer.strip():
                        events.append({"type": "thinking", "content": plan_buffer})
                    plan_emitted = True
                    plan_buffer = ""

            if tool_calls:
                for tc in tool_calls:
                    events.append({
                        "type": "tool_call",
                        "tool": tc["name"],
                        "args": tc["args"],
                    })
                content_acc = ""

            else:
                # No tool_calls + not a plan — this is a direct reply (content)
                if content_acc.strip():
                    events.append({"type": "message", "role": "assistant", "content": content_acc.strip()})
                content_acc = ""

                # ---- Card / Refs dispatch AFTER LLM has produced its response ----
                # The LLM has already streamed its natural-language summary.
                # Now emit structured UI events based on whether we have invoice data.
                if last_search_result:
                    if last_invoice_result:
                        # Scenario A: Reimbursement flow — has invoice + policy search
                        # Emit policy_card with judgment + confirmation_request
                        judgment = _synthesize_policy_judgment(
                            last_invoice_result, last_search_result, calculator=calculator_engine, rule_engine=rule_engine
                        )
                        card = build_policy_card(last_search_result, judgment)
                        events.append(card)
                        verdict = card["data"].get("verdict", "in_scope")
                        if verdict == "in_scope":
                            events.append({
                                "type": "confirmation_request",
                                "data": {
                                    "message": card["data"].get("summary", ""),
                                    "actions": ["confirm", "correct", "cancel"],
                                    "context": "policy_review",
                                },
                            })
                    else:
                        # Scenario B: Pure consultation — no invoice, AI already summarized
                        # Emit knowledge_refs (collapsible source citations only, no actions)
                        events.append({
                            "type": "knowledge_refs",
                            "data": {
                                "references": _extract_policy_refs(last_search_result),
                                "collapsed": True,
                            },
                        })
                    # Reset for next turn
                    last_invoice_result = None
                    last_search_result = None

        elif kind == "on_tool_end":
            raw = event["data"]["output"]
            result = _parse_tool_result(raw)
            tool_name = event["name"]
            has_error = isinstance(result, dict) and "error" in result

            # ---- Gateway: 过滤 Tool 结果（仅白名单字段进 LLM） ----
            gateway_result = result
            if security_gateway and isinstance(result, dict) and not has_error:
                try:
                    gateway_result = security_gateway.build_tool_result(tool_name, result)
                except Exception:
                    pass  # 过滤失败不阻塞流程

            events.append({
                "type": "tool_result",
                "tool": tool_name,
                "result": gateway_result,  # 清洗版发给前端
            })
            events.append({
                "type": "plan_step_update",
                "tool": tool_name,
                "status": "failed" if has_error else "done",
            })

            # Emit invoice_card after scan_invoice completes (data display only)
            if tool_name == "scan_invoice" and not has_error and isinstance(result, dict):
                last_invoice_result = result
                # invoice_card 用完整数据显示给用户（纯前端展示），但 LLM 只收到 gateway 版本
                card = build_invoice_card(result, {})   # 不再需要 desensitization
                events.append(card)

                # ---- Supplement form 检测 ----
                # scan_invoice 结果不完整时，检测是否需要补充信息
                if security_gateway and (not result.get('vendor') or result.get('vendor') == '未知商户'
                                         or not result.get('amount') or result.get('category_raw') == 'other'):
                    missing = []
                    if not result.get('vendor') or result.get('vendor') == '未知商户':
                        missing.append({'field': 'vendor', 'label': '商家/供应商', 'type': 'text', 'required': True})
                    if not result.get('amount'):
                        missing.append({'field': 'amount', 'label': '发票金额', 'type': 'number', 'required': True})
                    if result.get('category_raw') == 'other':
                        missing.append({
                            'field': 'category', 'label': '费用类别',
                            'type': 'select',
                            'required': True,
                            'options': [
                                {'value': 'meals', 'label': '餐饮'},
                                {'value': 'travel', 'label': '差旅'},
                                {'value': 'transportation', 'label': '交通'},
                                {'value': 'office_supplies', 'label': '办公用品'},
                                {'value': 'entertainment', 'label': '商务招待'},
                            ],
                        })
                    if missing:
                        events.append({
                            'type': 'supplement_form',
                            'data': {
                                'title': '请补充发票信息',
                                'fields': missing,
                                'hint': '此信息仅在本地处理，不会发送至云端',
                                'invoice_path': result.get('file_path', ''),
                            },
                        })

            # Record search_knowledge result — card/refs dispatch happens
            # AFTER the LLM has produced its natural-language summary
            if tool_name == "search_knowledge" and not has_error and isinstance(result, dict):
                last_search_result = result

    if content_acc.strip():
        events.append({"type": "message", "role": "assistant", "content": content_acc.strip()})

    events.append({"type": "done"})
    return events


def _build_desensitization(employee_id: int | None, user_id: int) -> dict:
    """Build desensitization info for card display. Returns {entity_type: {status, token}}."""
    if not employee_id:
        return {}
    try:
        from app.database import SessionLocal
        from app.services.desensitization_service import DesensitizationService
        db = SessionLocal()
        try:
            svc = DesensitizationService(db)
            result = svc.desensitize_employee(employee_id)
            tokens = result.get("tokens", {})
            return {
                key: {"status": "hidden", "token": token}
                for key, token in tokens.items()
            }
        finally:
            db.close()
    except Exception:
        return {}


def _extract_policy_refs(search_result: dict) -> list[dict]:
    """Extract source reference list from search_knowledge result for UI display."""
    refs = []
    for r in (search_result.get("results") or [])[:5]:
        refs.append({
            "source": r.get("filename", "未知文档"),
            "snippet": r.get("snippet", ""),
            "kb_name": r.get("kb_name", ""),
            "score": r.get("score", 0),
        })
    return refs


def _synthesize_policy_judgment(
    invoice_result: dict,
    search_result: dict,
    calculator: object | None = None,
    rule_engine: object | None = None,
) -> dict:
    """Synthesize LLM judgment from invoice and policy search results.

    New path (calculator present): deterministic calculation via CalculatorEngine.
    Legacy path (calculator=None): regex-based heuristic from hardcoded limits.

    In mock mode or when LLM hasn't explicitly judged, this provides a
    deterministic fallback based on policy snippet matching.
    """
    # ---- New path: CalculatorEngine ----
    if calculator is not None:
        return _synthesize_with_calculator(invoice_result, search_result, calculator, rule_engine=rule_engine)

    # ---- Legacy path (backward compatible) ----
    return _legacy_policy_judgment(invoice_result, search_result)


def _synthesize_with_calculator(
    invoice_result: dict,
    search_result: dict,
    calculator: object,
    rule_engine: object | None = None,
) -> dict:
    """Use CalculatorEngine for deterministic policy judgment."""
    category_raw = invoice_result.get("category_raw", "other")
    amount = invoice_result.get("amount", 0)

    calc = calculator.calculate(category_raw, amount)

    if calc.verdict == "out_of_scope":
        return {
            "verdict": "out_of_scope",
            "summary": f"该发票品类（{category_raw}）不在公司报销范围内。",
            "breakdown": None,
        }

    cap = calc.cap
    ratio = calc.reimbursement_ratio
    calculated = calc.calculated_amount
    final_amount = calc.final_amount

    cat_label = calc.expense_type_name or category_raw

    if cap and calculated > cap:
        summary = (
            f"{cat_label}报销：可报 {int(ratio * 100)}%，单次上限 {cap} 元。"
            f"发票 {amount} 元 → 预计报销 {final_amount} 元。"
        )
    elif ratio:
        summary = (
            f"{cat_label}报销：可报 {int(ratio * 100)}%。"
            f"发票 {amount} 元 → 预计报销 {calculated} 元。"
        )
    else:
        summary = f"{cat_label}在报销范围内。发票 {amount} 元，请确认是否提交报销。"

    # ---- RuleEngine overlay: enrich judgment with workflow flags ----
    rule_flags = {}
    if rule_engine is not None:
        try:
            rule_result = rule_engine.evaluate(category_raw, amount)
            rule_flags = {
                "can_submit": rule_result.can_submit,
                "need_approval": rule_result.need_approval,
                "need_guest_list": rule_result.need_guest_list,
                "need_invoice": rule_result.need_invoice,
                "need_attachment": rule_result.need_attachment,
            }
            # Append approval hint to summary
            if rule_result.need_approval:
                summary += f" 金额超过审批阈值，需主管审批。"
            if rule_result.need_guest_list:
                summary += f" 需提供宾客名单。"
            if rule_result.can_submit is False:
                return {
                    "verdict": "out_of_scope",
                    "summary": rule_result.reason,
                    "breakdown": None,
                }
        except Exception:
            pass  # RuleEngine evaluation failure is non-fatal

    return {
        "verdict": calc.verdict,
        "summary": summary,
        "breakdown": {
            "invoice_amount": amount,
            "reimbursement_rate": ratio,
            "calculated_amount": calculated,
            "cap": cap,
            "final_amount": final_amount,
            "rule_flags": rule_flags if rule_flags else None,
        },
    }


def _legacy_policy_judgment(invoice_result: dict, search_result: dict) -> dict:
    """Legacy fallback: regex-based judgment from hardcoded limits."""
    results = search_result.get("results", [])
    category_raw = invoice_result.get("category_raw", "other")
    amount = invoice_result.get("amount", 0)

    verdict = "in_scope"
    summary = ""
    breakdown = None

    # Try to find a matching policy snippet
    matched_snippet = ""
    for r in results:
        snippet = r.get("snippet", "")
        if category_raw in snippet.lower() or any(
            kw in snippet for kw in ["报销", "标准", "上限", "比例"]
        ):
            matched_snippet = snippet
            break

    if not matched_snippet and results:
        matched_snippet = results[0].get("snippet", "")

    # Build summary based on category
    category_labels = {
        "meals": "餐饮", "travel": "差旅", "transportation": "交通",
        "office_supplies": "办公用品", "entertainment": "商务招待",
    }
    cat_label = category_labels.get(category_raw, category_raw)

    if category_raw in ("meals", "travel", "transportation", "office_supplies", "entertainment"):
        # In-scope category
        verdict = "in_scope"
        # Try to extract policy limits from snippet
        rate, cap = _extract_policy_limits(matched_snippet, category_raw)
        calculated = round(amount * rate, 2) if rate else amount
        final_amount = min(calculated, cap) if cap else calculated

        if cap and calculated > cap:
            summary = (
                f"{cat_label}报销：可报 {int(rate*100)}%，单次上限 {cap} 元。"
                f"发票 {amount} 元 → 预计报销 {final_amount} 元。"
            )
        elif rate:
            summary = (
                f"{cat_label}报销：可报 {int(rate*100)}%。"
                f"发票 {amount} 元 → 预计报销 {calculated} 元。"
            )
        else:
            summary = f"{cat_label}在报销范围内。发票 {amount} 元，请确认是否提交报销。"

        breakdown = {
            "invoice_amount": amount,
            "reimbursement_rate": rate,
            "calculated_amount": calculated,
            "cap": cap,
            "final_amount": final_amount,
        }
    elif category_raw == "other":
        verdict = "out_of_scope"
        summary = f"未能识别发票品类（{cat_label}），请确认类别后重新查询。"
    else:
        verdict = "out_of_scope"
        summary = f"该发票品类（{cat_label}）不在公司报销范围内。"

    return {
        "verdict": verdict,
        "summary": summary,
        "breakdown": breakdown,
    }


def _extract_policy_limits(snippet: str, category: str) -> tuple[float, float | None]:
    """Extract reimbursement rate and cap from a policy snippet.

    Returns (rate, cap). rate is 0.0–1.0, cap is absolute amount or None.
    """
    import re

    rate = 0.6 if category == "meals" else 0.8  # default rates
    cap: float | None = None

    # Try to extract rate from snippet
    rate_match = re.search(r"(\d+)\s*%", snippet)
    if rate_match:
        rate = int(rate_match.group(1)) / 100.0

    # Try to extract cap/上限
    cap_match = re.search(r"(?:上限|不超过|≤)\s*(\d+)", snippet)
    if cap_match:
        cap = float(cap_match.group(1))

    # Category-specific defaults if not found in snippet
    if cap is None:
        defaults = {"meals": 500, "travel": 500, "transportation": 200, "office_supplies": 500, "entertainment": 1000}
        cap = defaults.get(category)

    return rate, cap


def _parse_tool_result(raw) -> dict | str:
    """Normalize tool output to dict if JSON, else string."""
    import json as _json
    if isinstance(raw, str):
        try:
            return _json.loads(raw)
        except (_json.JSONDecodeError, TypeError):
            return raw
    if isinstance(raw, ToolMessage):
        try:
            return _json.loads(raw.content) if isinstance(raw.content, str) else raw.content
        except (_json.JSONDecodeError, TypeError):
            return raw.content
    return str(raw)
