"""Expense reports API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import _parse_auth_header
from app.services.reimbursement_service import get_reimbursement_service
from app.infrastructure.orm import User, Employee
from app.domain.enums import ReportStatus

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("")
def list_my_expenses(
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    user = db.query(User).filter(User.id == auth["user_id"]).first()
    if not user or not user.employee_id:
        return []

    svc = get_reimbursement_service(db)
    reports = svc.list_by_employee(user.employee_id)

    return [
        {
            "id": r.id,
            "report_number": r.report_number,
            "total_amount": r.total_amount,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "submitted_at": str(r.submitted_at) if r.submitted_at else None,
            "created_at": str(r.created_at),
        }
        for r in reports
    ]


@router.get("/{report_id}")
def get_expense(report_id: int, db: Session = Depends(get_db)):
    svc = get_reimbursement_service(db)
    r = svc.get_report(report_id)
    if not r:
        raise HTTPException(status_code=404, detail="报销单不存在")
    return {
        "id": r.id,
        "report_number": r.report_number,
        "total_amount": r.total_amount,
        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        "rejection_reason": r.rejection_reason,
        "submitted_at": str(r.submitted_at) if r.submitted_at else None,
        "approved_at": str(r.approved_at) if r.approved_at else None,
        "paid_at": str(r.paid_at) if r.paid_at else None,
        "created_at": str(r.created_at),
    }


@router.get("/{report_id}/status")
def get_status(report_id: int, db: Session = Depends(get_db)):
    svc = get_reimbursement_service(db)
    r = svc.get_report(report_id)
    if not r:
        raise HTTPException(status_code=404, detail="报销单不存在")
    timeline = svc.get_timeline(report_id)
    return {
        "report_id": r.id,
        "report_number": r.report_number,
        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        "total_amount": r.total_amount,
        "timeline": timeline,
    }
