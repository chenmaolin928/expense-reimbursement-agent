"""Agent tools — public API for the ReAct agent.

Exports:
    get_all_tools()   → list of LangChain StructuredTools
    set_tool_context() → inject per-request context (user_id, employee_id, email)

Backward-compatible module-level tool instances (for tests that import tools by name):
    scan_invoice, search_knowledge, check_reimbursement_status,
    submit_reimbursement, send_notification
"""

from app.services.tools.base import set_tool_context, get_tool_context, BaseTool, ToolContext
from app.services.tools.scan_invoice import ScanInvoiceTool
from app.services.tools.search_knowledge import SearchKnowledgeTool
from app.services.tools.check_status import CheckStatusTool
from app.services.tools.submit_reimbursement import SubmitReimbursementTool
from app.services.tools.send_notification import SendNotificationTool


# --- Backward-compatible module-level instances ---

scan_invoice = ScanInvoiceTool().to_langchain_tool()
search_knowledge = SearchKnowledgeTool().to_langchain_tool()
check_reimbursement_status = CheckStatusTool().to_langchain_tool()
submit_reimbursement = SubmitReimbursementTool().to_langchain_tool()
send_notification = SendNotificationTool().to_langchain_tool()


# --- Tool registry for agent ---

def get_all_tools() -> list:
    """Return all agent tools as LangChain-compatible StructuredTools."""
    return [
        scan_invoice,
        search_knowledge,
        check_reimbursement_status,
        submit_reimbursement,
        send_notification,
    ]


__all__ = [
    "get_all_tools",
    "set_tool_context",
    "get_tool_context",
    "BaseTool",
    "ToolContext",
    "scan_invoice",
    "search_knowledge",
    "check_reimbursement_status",
    "submit_reimbursement",
    "send_notification",
    "ScanInvoiceTool",
    "SearchKnowledgeTool",
    "CheckStatusTool",
    "SubmitReimbursementTool",
    "SendNotificationTool",
]
