"""Reimbursement approval API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import _parse_auth_header
from app.services.reimbursement_service import get_reimbursement_service
from app.services.notification_service import get_notification_service
from app.domain.enums import ReportStatus

router = APIRouter(prefix="/reimbursements", tags=["reimbursements"])


class ApprovalBody(BaseModel):
    note: str = ""


@router.post("/{report_id}/approve")
def approve(
    report_id: int,
    body: ApprovalBody,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    # In a real system, check manager/finance role
    svc = get_reimbursement_service(db)
    report = svc.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报销单不存在")

    # Auto-advance: if submitted → manager_approval, if manager → approved
    next_status = {
        ReportStatus.SUBMITTED: ReportStatus.MANAGER_APPROVAL,
        ReportStatus.MANAGER_APPROVAL: ReportStatus.APPROVED,
        ReportStatus.FINANCE_APPROVAL: ReportStatus.APPROVED,
    }.get(report.status, None)

    if next_status is None:
        raise HTTPException(status_code=400, detail=f"当前状态 {report.status.value} 不可审批")

    result = svc.transition(
        report_id=report_id,
        new_status=next_status,
        triggered_by="manager",
        actor_id=auth["user_id"],
        note=body.note or "Approved",
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "审批失败"))

    # Handle final approval → auto-pay
    if next_status == ReportStatus.APPROVED:
        # Check if amount requires finance approval (skip for simplicity)
        svc.transition(
            report_id=report_id,
            new_status=ReportStatus.PAID,
            triggered_by="system",
            note="Auto-payment: amount within threshold",
        )
        result["new_status"] = ReportStatus.PAID.value

    # Notify
    notif_svc = get_notification_service(db)
    from app.infrastructure.orm import Employee
    emp = db.query(Employee).filter(Employee.id == report.employee_id).first()
    if emp:
        notif_svc.send(
            recipient_email=emp.email,
            event_type="approved",
            subject=f"报销审批通过 - {report.report_number}",
            body=f"您的报销单 {report.report_number} (¥{report.total_amount:.2f}) 已通过审批。",
            report_id=report.id,
        )

    return result


@router.post("/{report_id}/reject")
def reject(
    report_id: int,
    body: ApprovalBody,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    svc = get_reimbursement_service(db)
    report = svc.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报销单不存在")

    result = svc.transition(
        report_id=report_id,
        new_status=ReportStatus.REJECTED,
        triggered_by="manager",
        actor_id=auth["user_id"],
        note=body.note or "Rejected",
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "审批失败"))

    # Notify
    notif_svc = get_notification_service(db)
    from app.infrastructure.orm import Employee
    emp = db.query(Employee).filter(Employee.id == report.employee_id).first()
    if emp:
        notif_svc.send(
            recipient_email=emp.email,
            event_type="rejected",
            subject=f"报销申请被退回 - {report.report_number}",
            body=f"您的报销单 {report.report_number} 因以下原因被退回：{body.note or '未通过审批'}",
            report_id=report.id,
        )

    return result


@router.get("/{report_id}/timeline")
def get_timeline(report_id: int, db: Session = Depends(get_db)):
    svc = get_reimbursement_service(db)
    timeline = svc.get_timeline(report_id)
    return timeline
