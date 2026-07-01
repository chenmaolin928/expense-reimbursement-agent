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
    """After observe: if plan not complete, back to act; else end."""
    plan_complete = state.get("plan_complete", True)
    if plan_complete:
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
) -> list[dict]:
    """Run the PAO agent and return SSE events.

    Events: plan, thinking, tool_call, tool_result, plan_step_update, message, done
    """
    set_tool_context(user_id=user_id, employee_id=employee_id, user_email=user_email)

    agent = get_agent()
    input_messages: list = []

    if message_history:
        for m in message_history:
            if m["role"] == "user":
                input_messages.append(HumanMessage(content=_strip_attachment_markers(m["content"] or "")))
            elif m["role"] == "assistant":
                input_messages.append(AIMessage(content=m["content"] or ""))

    input_messages.append(HumanMessage(content=user_message))

    events: list[dict] = []
    config = {"configurable": {"thread_id": session_id}}
    content_acc = ""
    plan_emitted = False

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
                # Filter out plan JSON from streaming output
                if not plan_emitted and (token.strip().startswith("[{") or token.strip().startswith("```")):
                    continue
                content_acc += token
                events.append({"type": "thinking", "content": token})

        elif kind == "on_chat_model_end":
            output = event["data"]["output"]
            tool_calls = getattr(output, "tool_calls", None) or []

            # Check if this is plan output (from plan_node)
            if not plan_emitted and not tool_calls:
                plan = _parse_plan(str(output.content))
                if plan:
                    events.append({"type": "plan", "steps": plan})
                    plan_emitted = True
                    content_acc = ""
                    continue

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

        elif kind == "on_tool_end":
            raw = event["data"]["output"]
            result = _parse_tool_result(raw)
            tool_name = event["name"]
            has_error = isinstance(result, dict) and "error" in result
            events.append({
                "type": "tool_result",
                "tool": tool_name,
                "result": result,
            })
            events.append({
                "type": "plan_step_update",
                "tool": tool_name,
                "status": "failed" if has_error else "done",
            })

    if content_acc.strip():
        events.append({"type": "message", "role": "assistant", "content": content_acc.strip()})

    events.append({"type": "done"})
    return events


def _strip_attachment_markers(content: str) -> str:
    """Remove persisted upload markers from historical user messages.

    Attachments are turn-scoped. Leaving old markers in history makes later
    turns look like they still include uploaded files, which can wrongly bias
    both mock and real models toward invoice-scanning behavior.
    """
    text = str(content or "")
    prefixes = ("[已上传文件:", "[已上传文件：", "[Uploaded:", "[uploaded:")

    while True:
        stripped = text.lstrip()
        matched = False
        for prefix in prefixes:
            if stripped.startswith(prefix):
                line_end = stripped.find("\n")
                text = "" if line_end == -1 else stripped[line_end + 1 :]
                matched = True
                break
        if not matched:
            return text.lstrip()


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
