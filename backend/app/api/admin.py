"""Admin API routes — stats, employee management, PII cleanup."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import _parse_auth_header
from app.services.reimbursement_service import get_reimbursement_service
from app.services.desensitization_service import get_desensitization_service
from app.infrastructure.orm import Employee, User
from app.domain.enums import UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin(auth: dict = Depends(_parse_auth_header)):
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return True


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    __admin: bool = Depends(_check_admin),
):
    svc = get_reimbursement_service(db)
    stats = svc.get_stats()
    stats["total_employees"] = db.query(Employee).filter(Employee.is_active == True).count()
    stats["total_users"] = db.query(User).filter(User.is_active == True).count()
    return stats


@router.get("/employees")
def list_employees(
    db: Session = Depends(get_db),
    __admin: bool = Depends(_check_admin),
):
    emps = db.query(Employee).all()
    return [
        {
            "id": e.id,
            "employee_code": e.employee_code,
            "full_name": e.full_name,
            "email": e.email,
            "department": e.department,
            "bank_account": e.bank_account,
            "is_active": e.is_active,
        }
        for e in emps
    ]


@router.post("/pii/cleanup")
def cleanup_pii(
    db: Session = Depends(get_db),
    __admin: bool = Depends(_check_admin),
):
    svc = get_desensitization_service(db)
    count = svc.cleanup_expired()
    return {"deleted_count": count, "message": f"已清理 {count} 条过期 PII 映射"}
