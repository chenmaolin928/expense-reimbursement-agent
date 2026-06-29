"""Employee API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.infrastructure.orm import Employee

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("")
def list_employees(db: Session = Depends(get_db)):
    emps = db.query(Employee).filter(Employee.is_active == True).all()
    return [
        {
            "id": e.id,
            "employee_code": e.employee_code,
            "full_name": e.full_name,
            "department": e.department,
        }
        for e in emps
    ]


@router.get("/{employee_id}")
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="员工不存在")
    return {
        "id": e.id, "employee_code": e.employee_code,
        "full_name": e.full_name, "department": e.department,
        "email": e.email, "is_active": e.is_active,
    }
