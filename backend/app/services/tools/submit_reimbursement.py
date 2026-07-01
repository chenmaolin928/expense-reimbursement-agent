"""Submit reimbursement tool — create expense report in the internal system."""

from datetime import datetime
from pydantic import BaseModel, Field

from app.services.tools.base import BaseTool, get_tool_context


class SubmitReimbursementInput(BaseModel):
    report_id: str = Field(..., description="Internal report ID or generated reference")
    amount: float = Field(..., description="The approved reimbursement amount")
    category: str = Field(..., description="Policy category: travel, meals, office_supplies, transportation, entertainment")
    vendor: str = Field(..., description="The vendor/merchant name from the invoice")
    note: str = Field(default="", description="Optional note (e.g. reason for adjustment)")


class SubmitReimbursementTool(BaseTool):
    name = "submit_reimbursement"
    description = (
        "Submit a reimbursement request to the company's internal system. "
        "Use this AFTER: (1) scanned the invoice, (2) checked the policy, "
        "(3) confirmed the expense is reimbursable, (4) confirmed with the user. "
        "NEVER submit without user's explicit agreement."
    )
    args_schema = SubmitReimbursementInput

    def _run(self, report_id: str, amount: float, category: str, vendor: str, note: str = "") -> dict:
        from app.database import SessionLocal
        from app.infrastructure.orm import Employee, ExpenseReport, ExpenseItem, StatusTransition
        from app.domain.enums import ReportStatus, ExecutionStatus

        ctx = get_tool_context()
        employee_id = ctx.employee_id

        db = SessionLocal()
        try:
            if not employee_id:
                employee = db.query(Employee).first()
                employee_id = employee.id if employee else 1

            today = datetime.utcnow().strftime("%Y%m%d")
            count = db.query(ExpenseReport).count()
            report_number = f"EXP-{today}-{count + 1:04d}"

            report = ExpenseReport(
                report_number=report_number,
                employee_id=employee_id,
                total_amount=amount,
                status=ReportStatus.SUBMITTED,
                submitted_at=datetime.utcnow(),
            )
            db.add(report)
            db.flush()

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
