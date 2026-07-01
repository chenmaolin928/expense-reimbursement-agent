"""LLM client for the production DeepSeek integration.

Security boundary: this module handles all cloud LLM communication.
Runtime no longer falls back to a local mock. If DeepSeek is not configured,
startup/use must fail loudly so the operator knows the environment is broken.

The local mock model is retained only as a deterministic test helper.
"""

from langchain_deepseek import ChatDeepSeek

from app.config import settings

_model = None


def get_model():
    """Get the configured DeepSeek chat model.

    Raises:
        RuntimeError: DeepSeek API key is missing or still uses a placeholder.
    """
    global _model
    _ensure_deepseek_configured()
    if _model is None:
        _model = ChatDeepSeek(
            model=settings.deepseek.model,
            api_key=settings.deepseek.api_key,
            api_base=settings.deepseek.base_url,
            temperature=0.1,
            timeout=settings.agent.cloud_timeout_seconds,
        )
    return _model


def _ensure_deepseek_configured() -> None:
    """Fail fast when runtime LLM credentials are missing."""
    api_key = (settings.deepseek.api_key or "").strip()
    if not api_key or api_key.startswith("sk-placeholder"):
        raise RuntimeError(
            "DeepSeek API 未配置。请在 .env 中设置有效的 DEEPSEEK_API_KEY，"
            "当前运行时已禁止自动回退到 mock 模式。"
        )


# ---------------------------------------------------------------
# Test-only mock LLM
# ---------------------------------------------------------------

_CONFIRM_WORDS = [
    "ok",
    "yes",
    "confirm",
    "submit",
    "sure",
    "go ahead",
    "确认",
    "确认提交",
    "提交吧",
    "继续提交",
    "好的提交",
    "同意提交",
    "可以提交",
    "行，提交",
    "是的，提交",
    "agree",
    "approve",
    "proceed",
    "do it",
]


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
        last_user_has_attachment = False
        # Track which tool results came AFTER the LAST user message (this turn)
        # to avoid cross-turn pollution from previous completed workflows
        last_user_idx = -1

        for i, m in enumerate(messages):
            content = str(m.content) if hasattr(m, "content") and m.content else ""
            mtype = getattr(m, "type", None)

            if mtype == "human":
                last_user_msg = content
                last_user_idx = i
                last_user_has_attachment = _has_uploaded_attachment(content)

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
            if last_user_has_attachment:
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

        # 1: has attachment/reimbursement intent, no scan yet
        if last_user_has_attachment and "scan_invoice" not in tool_calls_made:
            return AIMessage(
                content="我先扫描这张发票，提取关键信息。",
                tool_calls=[{
                    "name": "scan_invoice",
                    "args": {"file_path": "data/invoices/uploaded_invoice.png"},
                    "id": "mock_scan_001",
                }],
            )

        # 2: scanned, but haven't checked policy yet
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
            is_confirm = _is_explicit_confirmation(last_user_msg)
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

        # 6: FAQ / knowledge question — ask before reimbursement flow
        faq_indicators = [
            "什么", "哪些", "怎么", "如何", "怎样", "哪个", "多少", "条件",
            "what", "which", "how", "when", "why", "who", "where",
            "类型", "种类", "分类", "规定", "要求", "是否需要",
        ]
        if any(kw in last_user_msg for kw in faq_indicators):
            return AIMessage(
                content=(
                    "关于您的问题，建议您上传报销相关的政策文档到知识库，"
                    "这样我可以帮您搜索具体的公司报销标准。\n\n"
                    "或者，如果您有具体的发票需要报销，请先上传发票图片，"
                    "我会帮您扫描并核实是否符合政策。"
                ),
            )

        # 7: fallback — reimbursement intent without attachment
        if any(kw in last_user_msg.lower() for kw in ("餐补", "政策", "标准", "policy", "meal", "allowance", "rule")):
            return AIMessage(
                content=(
                    "您好！关于公司餐补标准：\n\n"
                    "- 早餐：人均不超过 30 元\n"
                    "- 午餐：人均不超过 60 元\n"
                    "- 晚餐：人均不超过 100 元\n"
                    "- 单次报销上限：300 元（超限需经理审批）\n"
                    "- 必须附带小票或发票\n\n"
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


def _has_uploaded_attachment(content: str) -> bool:
    """Detect whether the CURRENT user turn explicitly contains uploaded files."""
    lowered = content.lower()
    return any(marker in content for marker in ("[已上传文件:", "[已上传文件：", "[Uploaded:")) or "[uploaded:" in lowered


def _is_explicit_confirmation(content: str) -> bool:
    """Treat only direct submit/confirm phrases as confirmation."""
    normalized = " ".join(str(content).lower().split())
    return any(word in normalized for word in _CONFIRM_WORDS)
