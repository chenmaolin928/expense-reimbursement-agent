"""Reimbursement state machine — simulates the company's internal system.

Handles: submit → manager_approval → finance_approval → approved → paid / rejected
Each transition is logged in status_transitions (immutable audit trail).
"""

from datetime import datetime
from sqlalchemy.orm import Session
from app.infrastructure.orm import ExpenseReport, StatusTransition
from app.domain.enums import ReportStatus


TRANSITIONS = {
    ReportStatus.DRAFT: [ReportStatus.SUBMITTED],
    ReportStatus.SUBMITTED: [ReportStatus.MANAGER_APPROVAL, ReportStatus.REJECTED],
    ReportStatus.MANAGER_APPROVAL: [ReportStatus.FINANCE_APPROVAL, ReportStatus.APPROVED, ReportStatus.REJECTED],
    ReportStatus.FINANCE_APPROVAL: [ReportStatus.APPROVED, ReportStatus.REJECTED],
    ReportStatus.APPROVED: [ReportStatus.PAID],
    ReportStatus.REJECTED: [],  # terminal
    ReportStatus.PAID: [],  # terminal
}


class ReimbursementService:
    """Internal reimbursement system simulator."""

    def __init__(self, db: Session):
        self.db = db

    def get_report(self, report_id: int) -> ExpenseReport | None:
        return self.db.query(ExpenseReport).filter(ExpenseReport.id == report_id).first()

    def get_report_by_number(self, report_number: str) -> ExpenseReport | None:
        return self.db.query(ExpenseReport).filter(
            ExpenseReport.report_number == report_number
        ).first()

    def transition(
        self,
        report_id: int,
        new_status: ReportStatus,
        triggered_by: str,
        actor_id: int | None = None,
        note: str | None = None,
    ) -> dict:
        """Attempt to transition a report to a new status.

        Returns {"success": True, "new_status": ...} or {"success": False, "error": ...}
        """
        report = self.get_report(report_id)
        if not report:
            return {"success": False, "error": f"Report {report_id} not found"}

        old_status = report.status
        allowed = TRANSITIONS.get(old_status, [])

        if new_status not in allowed:
            return {
                "success": False,
                "error": f"Cannot transition from {old_status.value} to {new_status.value}",
            }

        # Record transition
        t = StatusTransition(
            report_id=report.id,
            from_status=old_status.value,
            to_status=new_status.value,
            triggered_by=triggered_by,
            actor_id=actor_id,
            note=note,
        )
        self.db.add(t)

        # Apply state change
        report.status = new_status
        if new_status == ReportStatus.REJECTED and note:
            report.rejection_reason = note
        if new_status == ReportStatus.APPROVED:
            report.approved_at = datetime.utcnow()
        if new_status == ReportStatus.PAID:
            report.paid_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(report)

        return {
            "success": True,
            "report_id": report.id,
            "report_number": report.report_number,
            "old_status": old_status.value,
            "new_status": new_status.value,
        }

    def get_timeline(self, report_id: int) -> list[dict]:
        """Get full status transition history for a report."""
        transitions = (
            self.db.query(StatusTransition)
            .filter(StatusTransition.report_id == report_id)
            .order_by(StatusTransition.created_at.asc())
            .all()
        )
        return [
            {
                "id": t.id,
                "from_status": t.from_status,
                "to_status": t.to_status,
                "triggered_by": t.triggered_by,
                "actor_id": t.actor_id,
                "note": t.note,
                "created_at": str(t.created_at),
            }
            for t in transitions
        ]

    def list_by_employee(self, employee_id: int):
        return (
            self.db.query(ExpenseReport)
            .filter(ExpenseReport.employee_id == employee_id)
            .order_by(ExpenseReport.created_at.desc())
            .all()
        )

    def get_stats(self) -> dict:
        """Dashboard statistics."""
        reports = self.db.query(ExpenseReport)
        total = reports.count()
        by_status = {}
        for status in ReportStatus:
            by_status[status.value] = reports.filter(ExpenseReport.status == status).count()
        total_amount = sum(r.total_amount for r in reports.all() if r.total_amount)

        return {
            "total_reports": total,
            "by_status": by_status,
            "total_reimbursed": total_amount,
        }


def get_reimbursement_service(db: Session) -> ReimbursementService:
    return ReimbursementService(db)
