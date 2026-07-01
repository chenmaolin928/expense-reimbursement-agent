"""LLM client — supports both real DeepSeek and local mock mode.

Security boundary: this module handles all cloud LLM communication.
When MOCK_MODE is True, uses a local mock that simulates DeepSeek behavior
so you can test the full ReAct agent loop without an API key.

Mock mode produces realistic function_call sequences — this is NOT a
hardcoded workflow. The agent graph still decides the path.
"""

from langchain_deepseek import ChatDeepSeek
from app.config import settings

_model = None
_mock_model = None

MOCK_MODE = (
    not settings.deepseek.api_key
    or settings.deepseek.api_key.startswith("sk-placeholder")
)


def get_model():
    """Get chat model — real DeepSeek or mock."""
    global _model, _mock_model
    if MOCK_MODE:
        if _mock_model is None:
            _mock_model = _MockChatModel()
        return _mock_model
    if _model is None:
        _model = ChatDeepSeek(
            model=settings.deepseek.model,
            api_key=settings.deepseek.api_key,
            api_base=settings.deepseek.base_url,
            temperature=0.1,
            timeout=settings.agent.cloud_timeout_seconds,
        )
    return _model


# ---------------------------------------------------------------
# Mock LLM — simulates DeepSeek's ReAct reasoning locally
# ---------------------------------------------------------------

_CONFIRM_WORDS = [
    "ok", "yes", "confirm", "submit", "sure", "go ahead",
    "确认", "提交", "好的", "可以", "行", "是的", "对", "报销",
    "agree", "approve", "proceed", "do it", "please",
]


def _extract_first_pending_tool(messages) -> tuple[str | None, dict]:
    """Extract the first unexecuted tool from a plan_node AIMessage if present.

    The plan_node writes a JSON array into an AIMessage like:
        [{"step": "...", "tool": "search_knowledge", "args": {"query": "..."}}]

    This helper parses the last such plan message and finds the first tool
    whose name hasn't appeared in tool_calls yet.
    """
    import json as _json
    import re

    tool_calls_made: set[str] = set()
    plan_json_str = None

    for m in messages:
        # Collect tool calls already made
        tcs = getattr(m, "tool_calls", None) or []
        for tc in tcs:
            tool_calls_made.add(tc.get("name", ""))

        # Find the last plan_node output
        content = str(m.content) if hasattr(m, "content") and m.content else ""
        stripped = content.strip()
        if stripped.startswith("[{") or stripped.startswith("[") and not stripped.startswith("[]"):
            plan_json_str = stripped

    if not plan_json_str:
        return None, {}

    # Remove markdown fences if present
    if plan_json_str.startswith("```"):
        plan_json_str = re.sub(r"^```\w*\n?", "", plan_json_str)
        plan_json_str = re.sub(r"\n?```$", "", plan_json_str)

    try:
        plan = _json.loads(plan_json_str)
        if isinstance(plan, list):
            for step in plan:
                tool = step.get("tool", "")
                if tool and tool not in tool_calls_made:
                    return tool, step.get("args", {})
    except (_json.JSONDecodeError, TypeError):
        pass

    return None, {}


class _MockChatModel:
    """Simulated LLM that produces tool-call sequences for ReAct loops.

    Traces conversations to decide which tool to call next — exactly
    what DeepSeek would do, but deterministic for demo purposes.
    """

    def __init__(self):
        self._tools = {}

    def bind_tools(self, tools):
        self._tools = {t.name: t for t in tools}
        return self

    def invoke(self, messages):
        from langchain_core.messages import AIMessage
        return self._decide(messages)

    async def astream(self, messages, **kwargs):
        """Simulate streaming token by token — enables on_chat_model_stream events."""
        import asyncio
        from langchain_core.messages import AIMessageChunk

        response = self._decide(messages)
        content = str(response.content) if response.content else ""
        tool_calls = getattr(response, "tool_calls", None) or []

        if tool_calls:
            # Emit content first, then tool_calls chunk
            if content:
                yield AIMessageChunk(content=content)
            # Build tool_call_chunks for proper streaming merge
            tc_chunks = []
            for tc in tool_calls:
                tc_chunks.append({
                    "name": tc.get("name"),
                    "args": tc.get("args", {}),
                    "id": tc.get("id"),
                    "index": 0,
                })
            yield AIMessageChunk(content="", tool_call_chunks=tc_chunks)
        else:
            # Stream content in small chunks for real-time feel
            for i in range(0, len(content), 3):
                yield AIMessageChunk(content=content[i:i+3])
                await asyncio.sleep(0.005)

    def _decide(self, messages):
        """Decision engine — shared by invoke() and astream()."""
        from langchain_core.messages import AIMessage

        tool_calls_made: list[str] = []
        has_tool_result: dict[str, bool] = {}
        last_user_msg = ""
        last_system_msg = ""
        has_attachment = False
        # Track which tool results came AFTER the LAST user message (this turn)
        # to avoid cross-turn pollution from previous completed workflows
        last_user_idx = -1

        for i, m in enumerate(messages):
            content = str(m.content) if hasattr(m, "content") and m.content else ""
            mtype = getattr(m, "type", None)

            if mtype == "human":
                last_user_msg = content
                last_user_idx = i
                # Only trigger has_attachment if user ACTUALLY uploaded a file
                if any(kw in content for kw in ("[已上传文件:", "[Uploaded:", "[已上传文件：", "[uploaded:")):
                    has_attachment = True
                if any(kw in content for kw in ("发票", "invoice", "receipt")) and \
                   ("上传" in content or "[Uploaded" in content or "[已上传" in content):
                    has_attachment = True

            elif mtype == "tool":
                # Only count tool results from THIS turn (after last user message)
                if last_user_idx >= 0 and i > last_user_idx:
                    tool_name = getattr(m, "name", "")
                    if tool_name:
                        has_tool_result[tool_name] = True

            elif mtype == "ai":
                # Only count tool_calls from THIS turn
                if last_user_idx >= 0 and i > last_user_idx:
                    tcs = getattr(m, "tool_calls", None) or []
                    for tc in tcs:
                        tool_calls_made.append(tc["name"])

            elif mtype == "system":
                last_system_msg = content

        # 0: Detect plan prompt → return JSON plan (Chinese PLAN_PROMPT)
        if last_system_msg and "任务编排器" in last_system_msg:
            if any(kw in last_user_msg.lower() for kw in ("餐补", "政策", "标准", "policy", "meal", "allowance", "rule")):
                return AIMessage(content='[{"step": "搜索报销政策", "tool": "search_knowledge", "args": {"query": "报销标准 餐饮"}, "status": "pending"}]')
            if has_attachment:
                return AIMessage(
                    content=(
                        '[{"step": "扫描发票提取关键信息", "tool": "scan_invoice", "args": {"file_path": "data/invoices/uploaded_invoice.png"}, "status": "pending"},'
                        '{"step": "查询公司报销政策", "tool": "search_knowledge", "args": {"query": "报销标准 办公用品 餐饮 差旅"}, "status": "pending"}]'
                    ),
                )
            if any(kw in last_user_msg.lower() for kw in ("报销", "reimburse", "发票", "invoice")):
                # User wants reimbursement but has no attachment — empty plan, respond directly
                return AIMessage(content="[]")
            if any(kw in last_user_msg.lower() for kw in ("状态", "进度", "status", "查询", "check")):
                return AIMessage(content='[{"step": "查询报销状态", "tool": "check_reimbursement_status", "args": {"report_number": "EXP-unknown"}, "status": "pending"}]')
            # FAQ: "什么/怎么/哪些/如何/..." — search knowledge base
            if any(kw in last_user_msg for kw in ("什么", "哪些", "怎么", "如何", "怎样", "哪个", "多少", "条件",
                                                       "能否", "可以", "是不是", "需不需要", "要不要")):
                return AIMessage(content='[{"step": "搜索相关知识", "tool": "search_knowledge", "args": {"query": "' + last_user_msg[:50] + '"}, "status": "pending"}]')
            # Catch-all: casual chat
            return AIMessage(content="[]")

        # 1: Detect plan steps from plan_node output — execute the FIRST pending tool
        # The plan_node emits JSON like [{"tool": "search_knowledge", "args": {...}}]
        # which is stored in an AIMessage. When the act_node runs, we must honour it.
        plan_tool, plan_args = _extract_first_pending_tool(messages)
        if plan_tool and plan_tool not in tool_calls_made:
            return AIMessage(
                content=f"好的，让我来查询相关信息。",
                tool_calls=[{
                    "name": plan_tool,
                    "args": plan_args,
                    "id": f"mock_plan_{plan_tool}_001",
                }],
            )

        # 2: has attachment/reimbursement intent, no scan yet
        if has_attachment and "scan_invoice" not in tool_calls_made:
            return AIMessage(
                content="我先扫描这张发票，提取关键信息。",
                tool_calls=[{
                    "name": "scan_invoice",
                    "args": {"file_path": "data/invoices/uploaded_invoice.png"},
                    "id": "mock_scan_001",
                }],
            )

        # 3: scanned, but haven't checked policy yet
        if has_tool_result.get("scan_invoice") and "search_knowledge" not in tool_calls_made:
            return AIMessage(
                content="发票信息已提取，让我查询公司报销政策。",
                tool_calls=[{
                    "name": "search_knowledge",
                    "args": {"query": "报销标准 餐饮 办公用品 差旅"},
                    "id": "mock_search_001",
                }],
            )

        # 3: scanned + policy checked, but not submitted — ask for confirmation
        if (
            has_tool_result.get("scan_invoice")
            and has_tool_result.get("search_knowledge")
            and "submit_reimbursement" not in tool_calls_made
        ):
            is_confirm = any(kw in last_user_msg.lower() for kw in _CONFIRM_WORDS)
            if is_confirm:
                return AIMessage(
                    content="收到确认，正在提交报销申请...",
                    tool_calls=[{
                        "name": "submit_reimbursement",
                        "args": {
                            "report_id": "REQ-auto-001",
                            "amount": 234.50,
                            "category": "office_supplies",
                            "vendor": "Office Depot",
                            "note": "办公用品报销，符合公司政策",
                        },
                        "id": "mock_submit_001",
                    }],
                )

            return AIMessage(
                content=(
                    "根据扫描结果和公司政策，我分析如下：\n\n"
                    "[发票信息] 金额 234.50，类别 办公用品\n"
                    "[政策匹配] 办公用品单次报销上限 2000，单项不超过 500\n\n"
                    "该发票在报销范围内，金额 234.50 未超限。\n\n"
                    "是否确认提交报销？确认后我将提交到公司内部报销系统。"
                ),
            )

        # 4: submitted, but not notified
        if (
            has_tool_result.get("submit_reimbursement")
            and "send_notification" not in tool_calls_made
        ):
            return AIMessage(
                content="报销已提交，正在发送邮件通知...",
                tool_calls=[{
                    "name": "send_notification",
                    "args": {
                        "subject": "报销申请已提交 - EXP-2026-0001",
                        "body": "您的报销申请已成功提交，金额 234.50，当前状态：等待审批。",
                    },
                    "id": "mock_notify_001",
                }],
            )

        # 5: all done
        if has_tool_result.get("send_notification"):
            return AIMessage(
                content=(
                    "报销流程已完成！\n\n"
                    "您的报销单已提交至公司内部系统，审批完成后会邮件通知您。\n"
                    "如需查询进度，随时问我。"
                ),
            )

        # 6: search_knowledge result received (pure policy question, not reimbursement flow)
        if has_tool_result.get("search_knowledge") and "scan_invoice" not in tool_calls_made:
            # AI should summarise policy based on the tool result content.
            # Since mock mode cannot read ToolMessage content, we guide the user
            # to the knowledge_refs card while encouraging real LLM summarisation.
            return AIMessage(
                content=(
                    "根据知识库中的搜索结果，以下是与您查询相关的公司报销政策摘要。\n\n"
                    "请展开下方的「来源引用」卡片查看具体的政策条款和原文。\n\n"
                    "（提示：如果这是真实 DeepSeek 模式，AI 会根据知识库内容自动总结政策要点，包括金额标准、报销比例、上限和特殊条件。）"
                ),
            )

        # 7: fallback — pure policy question without any tool history
        if any(kw in last_user_msg.lower() for kw in ("餐补", "政策", "标准", "policy", "meal", "allowance", "rule")):
            return AIMessage(
                content=(
                    "您好！关于公司政策的查询，我正在为您搜索知识库中的相关内容。\n\n"
                    "请展开下方的「来源引用」卡片查看具体的政策条款和原文摘要。\n"
                    "（在真实 DeepSeek 模式下，AI 会根据搜索结果自动总结政策要点。）\n\n"
                    "如果您有发票需要报销，请上传后告诉我！"
                ),
            )

        # 7: fallback — reimbursement intent without attachment
        if any(kw in last_user_msg.lower() for kw in ("报销", "reimburse", "发票", "invoice", "receipt", "帮我处理")):
            return AIMessage(
                content=(
                    "好的，我看到您想处理报销。请您先上传发票或收据图片，"
                    "我会帮您扫描并提取关键信息，再根据公司政策帮您判断是否可以报销。\n\n"
                    "请点击输入框左侧的📎按钮上传文件。"
                ),
            )

        # 8: true fallback
        return AIMessage(
            content=(
                "您好！我是报销助手小报。您可以：\n"
                "1. 上传发票图片，我会帮您处理报销\n"
                "2. 直接问我公司报销政策\n"
                "3. 查询已有报销单的状态\n\n"
                "请问有什么可以帮您？"
            ),
        )
