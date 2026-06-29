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
    not settings.deepseek_api_key
    or settings.deepseek_api_key.startswith("sk-placeholder")
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
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            api_base=settings.deepseek_base_url,
            temperature=0.1,
            timeout=settings.agent_cloud_timeout_seconds,
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

        # ---- Scan conversation history ----
        tool_calls_made: list[str] = []
        has_tool_result: dict[str, bool] = {}
        last_user_msg = ""
        has_attachment = False

        for m in messages:
            content = str(m.content) if hasattr(m, "content") and m.content else ""
            mtype = getattr(m, "type", None)

            if mtype == "human":
                # Use the LAST human message for confirmation detection
                last_user_msg = content
                if any(kw in content for kw in ("上传", "发票", "invoice", "attachment", "receipt", "报销", "reimburse")):
                    has_attachment = True

            elif mtype == "tool":
                tool_name = getattr(m, "name", "")
                if tool_name:
                    has_tool_result[tool_name] = True

            elif mtype == "ai":
                tcs = getattr(m, "tool_calls", None) or []
                for tc in tcs:
                    tool_calls_made.append(tc["name"])

        # ---- Decision engine (mock LLM reasoning) ----

        # 1: has attachment/reimbursement intent, no scan yet
        if has_attachment and "scan_invoice" not in tool_calls_made:
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
            # Check if user just confirmed
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

        # 6: pure knowledge/policy question
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

        # 7: fallback
        return AIMessage(
            content=(
                "您好！我是报销助手小报。您可以：\n"
                "1. 上传发票图片，我会帮您处理报销\n"
                "2. 直接问我公司报销政策\n"
                "3. 查询已有报销单的状态\n\n"
                "请问有什么可以帮您？"
            ),
        )
