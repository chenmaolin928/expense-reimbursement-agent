"""Check reimbursement status tool — look up expense report progress."""

from pydantic import BaseModel, Field

from app.services.tools.base import BaseTool


class CheckStatusInput(BaseModel):
    report_number: str = Field(..., description="The reimbursement report number (e.g. 'EXP-2026-0042')")


class CheckStatusTool(BaseTool):
    name = "check_reimbursement_status"
    description = (
        "Check the approval status of a submitted reimbursement report. "
        "Use this when a user asks about the status of their expense report."
    )
    args_schema = CheckStatusInput

    def _run(self, report_number: str) -> dict:
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
