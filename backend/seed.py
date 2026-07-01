"""Seed the database with demo data — employees, users, policy rules."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, Base, SessionLocal
from app.infrastructure.orm import Employee, User
from app.domain.enums import UserRole
from app.config import settings
import hashlib


def _hash_password(password: str) -> str:
    salt = "expense-agent-salt-v1"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


# Ensure data dir exists
os.makedirs(settings.storage.invoice_storage_path, exist_ok=True)

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Skip if already seeded
    if db.query(Employee).count() > 0:
        print("Database already seeded. Skipping.")
        db.close()
        sys.exit(0)

    # --- Employees ---
    admin_emp = Employee(
        employee_code="EMP-00001",
        full_name="System Admin",
        email="admin@company.cn",
        department="IT",
        bank_account="6222-0000-0000-0001",
    )
    emp_zhang = Employee(
        employee_code="EMP-00142",
        full_name="Zhang Wei",
        email="zhangwei@company.cn",
        department="Engineering",
        bank_account="6222-0000-0000-0042",
    )
    emp_li = Employee(
        employee_code="EMP-00005",
        full_name="Li Ming",
        email="liming@company.cn",
        department="Engineering",
        bank_account="6222-0000-0000-0005",
    )
    db.add_all([admin_emp, emp_zhang, emp_li])
    db.flush()

    # Set manager relationship
    emp_zhang.manager_id = emp_li.id
    emp_li.manager_id = admin_emp.id
    db.flush()

    # --- Users ---
    users = [
        User(
            username="admin",
            password_hash=_hash_password("admin123"),
            role=UserRole.ADMIN,
            employee_id=admin_emp.id,
        ),
        User(
            username="zhangwei",
            password_hash=_hash_password("zhang123"),
            role=UserRole.EMPLOYEE,
            employee_id=emp_zhang.id,
        ),
        User(
            username="liming",
            password_hash=_hash_password("li123"),
            role=UserRole.EMPLOYEE,
            employee_id=emp_li.id,
        ),
    ]
    db.add_all(users)

    db.commit()
    print("Database seeded successfully!")
    print(f"  Employees: {db.query(Employee).count()}")
    print(f"  Users: {db.query(User).count()}")

finally:
    db.close()
