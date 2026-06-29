"""Agent tool definitions — Cloud LLM decision tools executed LOCALLY.

CRITICAL: These tools are defined here with their OpenAI-format schemas.
The LLM sees ONLY the function name, description, and parameter schema.
The LLM does NOT see: API URLs, auth tokens, database connections, employee PII.

Security boundary: tool execution happens inside the FastAPI process (internal network).
Only the function_call request goes to DeepSeek; tool results return to the LLM
but contain ONLY desensitized/necessary data.
"""

from datetime import datetime
from typing import Any

from langchain_core.tools import tool


# --- Module-level registry for injecting services at request time ---
# This avoids passing services through every LangGraph node.
_registry: dict[str, Any] = {}


def set_tool_context(**kwargs) -> None:
    """Set service references for tool execution. Called at request time."""
    _registry.update(kwargs)


def _get_db():
    return _registry.get("db")


def _get_user_id():
    return _registry.get("user_id")


def _get_employee_id():
    return _registry.get("employee_id")


def _get_user_email():
    return _registry.get("user_email")


# ============================================================
# TOOL DEFINITIONS — These function names/descriptions/schemas
# are what DeepSeek sees. The LLM does NOT see the function body.
# ============================================================


@tool
def scan_invoice(file_path: str) -> dict:
    """Simulated OCR: Scan an invoice file and extract structured data.

    Use this whenever a user uploads an invoice/receipt image or PDF.
    Returns vendor name, amount, date, category, and line items.
    Always call this FIRST before making any reimbursement decisions.

    Args:
        file_path: Path to the uploaded invoice file (e.g. 'data/invoices/invoice_001.png')

    Returns:
        dict with keys: vendor, amount, currency, date, category_raw, line_items
    """
    # In production, this would call PaddleOCR/Tesseract
    # Currently SIMULATED — returns mock data based on file_path hash for variety

    import hashlib

    hash_val = int(hashlib.md5(file_path.encode()).hexdigest()[:8], 16)

    categories = ["office_supplies", "meals", "travel", "transportation", "entertainment"]
    vendors = {
        "office_supplies": ["Office Depot", "Staples", "晨光文具"],
        "meals": ["海底捞", "星巴克", "麦当劳", "鼎泰丰"],
        "travel": ["汉庭酒店", "如家", "锦江之星", "7天连锁"],
        "transportation": ["滴滴出行", "曹操出行"],
        "entertainment": ["俏江南", "大董烤鸭"],
    }
    cat = categories[hash_val % len(categories)]
    vendor = vendors[cat][hash_val % len(vendors[cat])]

    amounts = [45.00, 128.50, 234.50, 380.00, 520.00, 890.00, 1250.00, 2800.00]
    amount = amounts[hash_val % len(amounts)]

    return {
        "file_path": file_path,
        "vendor": vendor,
        "amount": amount,
        "currency": "CNY",
        "date": "2026-06-25",
        "category_raw": cat,
        "line_items": [{"description": f"{vendor} purchase", "total": amount}],
    }


@tool
def search_knowledge(query: str) -> dict:
    """Search company reimbursement policy knowledge base.

    Use this to look up policy rules BEFORE making reimbursement decisions.
    Always search for the specific category (e.g. 'meals', 'travel', 'office_supplies')
    and compare the invoice amount against policy limits.

    Args:
        query: Search query string (e.g. '餐饮报销标准', 'office supplies policy', '差旅住宿标准')

    Returns:
        dict with: total_results, results (list of {snippet, kb_name, filename})
    """
    from app.database import SessionLocal
    from app.services.knowledge_service import KnowledgeService

    db = SessionLocal()
    try:
        svc = KnowledgeService(db)
        results = svc.search(query)
        return {
            "total_results": len(results),
            "results": [
                {"snippet": r["snippet"], "kb_name": r["kb_name"], "filename": r["filename"]}
                for r in results[:5]
            ],
        }
    finally:
        db.close()


@tool
def check_reimbursement_status(report_number: str) -> dict:
    """Check the approval status of a submitted reimbursement report.

    Use this when a user asks about the status of their expense report.

    Args:
        report_number: The reimbursement report number (e.g. 'EXP-2026-0042')

    Returns:
        dict with: report_number, status, total_amount, submitted_at, timeline
    """
    from app.database import SessionLocal
    from app.infrastructure.orm import ExpenseReport, StatusTransition

    db = SessionLocal()
    try:
        report = db.query(ExpenseReport).filter(
            ExpenseReport.report_number == report_number
        ).first()
        if not report:
            return {"error": f"未找到报销单 {report_number}"}

        transitions = (
            db.query(StatusTransition)
            .filter(StatusTransition.report_id == report.id)
            .order_by(StatusTransition.created_at.asc())
            .all()
        )

        return {
            "report_number": report.report_number,
            "status": report.status.value if hasattr(report.status, "value") else str(report.status),
            "total_amount": report.total_amount,
            "submitted_at": str(report.submitted_at) if report.submitted_at else None,
            "timeline": [
                {
                    "from": t.from_status,
                    "to": t.to_status,
                    "at": str(t.created_at),
                    "by": t.triggered_by,
                }
                for t in transitions
            ],
        }
    finally:
        db.close()


@tool
def submit_reimbursement(
    report_id: str,
    amount: float,
    category: str,
    vendor: str,
    note: str = "",
) -> dict:
    """Submit a reimbursement request to the company's internal system.

    Use this AFTER:
    1. Scanned the invoice (scan_invoice)
    2. Checked the policy (search_knowledge)
    3. Confirmed the expense is reimbursable
    4. Confirmed with the user that they want to submit

    IMPORTANT: Must have user confirmation before calling this tool.
    NEVER submit without user's explicit agreement.

    Args:
        report_id: Internal report ID or generated reference
        amount: The approved reimbursement amount (may differ from invoice amount)
        category: The policy category (travel, meals, office_supplies, transportation, entertainment)
        vendor: The vendor/merchant name from the invoice
        note: Optional note (e.g. reason for adjustment, flags)

    Returns:
        dict with: report_number, status, message
    """
    from app.database import SessionLocal
    from app.infrastructure.orm import (
        Employee, ExpenseReport, ExpenseItem, StatusTransition,
    )
    from app.domain.enums import ReportStatus, ExecutionStatus

    db = SessionLocal()
    try:
        # Get employee from context
        employee_id = _get_employee_id()
        if not employee_id:
            employee = db.query(Employee).first()
            employee_id = employee.id if employee else 1

        # Generate report number
        today = datetime.utcnow().strftime("%Y%m%d")
        count = db.query(ExpenseReport).count()
        report_number = f"EXP-{today}-{count + 1:04d}"

        # Create report
        report = ExpenseReport(
            report_number=report_number,
            employee_id=employee_id,
            total_amount=amount,
            status=ReportStatus.SUBMITTED,
            submitted_at=datetime.utcnow(),
        )
        db.add(report)
        db.flush()

        # Create item
        item = ExpenseItem(
            report_id=report.id,
            invoice_path=f"chat-upload:{report_id}",
            ocr_vendor=vendor,
            ocr_amount=amount,
            ocr_date=datetime.utcnow().date(),
            ocr_category_raw=category,
            cloud_decision_status="approved",
            cloud_decision_category=category,
            cloud_approved_amount=amount,
            execution_status=ExecutionStatus.FORM_FILLED,
        )
        db.add(item)

        # Record transition
        transition = StatusTransition(
            report_id=report.id,
            from_status=None,
            to_status=ReportStatus.SUBMITTED.value,
            triggered_by="cloud_agent",
            note=note or f"AI Agent auto-submitted: {category} {amount:.2f} CNY at {vendor}",
        )
        db.add(transition)

        db.commit()

        return {
            "report_number": report_number,
            "status": ReportStatus.SUBMITTED.value,
            "amount": amount,
            "category": category,
            "message": f"报销单 {report_number} 已提交，金额 ¥{amount:.2f}，等待审批",
        }
    finally:
        db.close()


@tool
def send_notification(subject: str, body: str) -> dict:
    """Send email notification to the current user about their reimbursement status.

    Use this at the end of processing to notify the user of the outcome.
    The system automatically determines the recipient email — DO NOT ask for it.

    Args:
        subject: Email subject line
        body: Email body content

    Returns:
        dict with: sent, recipient, subject
    """
    from app.database import SessionLocal
    from app.infrastructure.orm import NotificationLog

    recipient = _get_user_email() or "employee@company.cn"

    db = SessionLocal()
    try:
        log = NotificationLog(
            recipient_email=recipient,
            event_type="agent_notification",
            subject=subject,
            body=body,
        )
        db.add(log)
        db.commit()

        return {"sent": True, "recipient": recipient, "subject": subject}
    finally:
        db.close()
