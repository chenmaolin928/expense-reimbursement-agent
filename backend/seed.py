"""Seed the database with demo data — employees, users, policy rules."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, Base, SessionLocal
from app.infrastructure.orm import Employee, User, Policy, PolicyVersion
from app.domain.enums import UserRole, PolicyStatus
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
    db.flush()

    # --- Default policy rules (new domains[].rules[] format) ---
    # Write policy JSON to file storage so RuleEngine can find it
    os.makedirs(settings.policy.policies_dir, exist_ok=True)

    default_policy_json = {
        "doc_id": "",
        "title": "默认公司报销政策",
        "version": "1.0",
        "domains": [
            {
                "id": "meals", "name": "餐饮",
                "rules": [
                    {"id": "meals_ratio", "type": "ratio", "title": "餐饮报销比例",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 0.6, "unit": "percent",
                     "raw_text": "餐饮报销比例为60%"},
                    {"id": "meals_cap", "type": "limit", "title": "餐饮单次上限",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 300, "unit": "yuan",
                     "raw_text": "餐饮单次报销不超过300元"},
                    {"id": "meals_ppl", "type": "limit", "title": "餐饮人均限额",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 100, "unit": "yuan",
                     "raw_text": "餐饮人均不超过100元"},
                    {"id": "meals_approval", "type": "approval", "title": "餐饮审批阈值",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "超过200元", "value": 200, "unit": "yuan",
                     "raw_text": "餐饮超过200元需审批"},
                ]
            },
            {
                "id": "travel", "name": "差旅",
                "rules": [
                    {"id": "travel_ratio", "type": "ratio", "title": "差旅报销比例",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 0.8, "unit": "percent",
                     "raw_text": "差旅报销比例为80%"},
                    {"id": "travel_cap", "type": "limit", "title": "差旅单次上限",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 2000, "unit": "yuan",
                     "raw_text": "差旅单次报销不超过2000元"},
                    {"id": "travel_ppl", "type": "limit", "title": "差旅人均限额",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 500, "unit": "yuan",
                     "raw_text": "差旅人均不超过500元"},
                    {"id": "travel_approval", "type": "approval", "title": "差旅审批阈值",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "超过1000元", "value": 1000, "unit": "yuan",
                     "raw_text": "差旅超过1000元需审批"},
                    {"id": "travel_attachment", "type": "requirement", "title": "差旅需附件",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": None, "unit": "",
                     "raw_text": "差旅需要附件"},
                ]
            },
            {
                "id": "transportation", "name": "交通",
                "rules": [
                    {"id": "trans_ratio", "type": "ratio", "title": "交通报销比例",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 0.7, "unit": "percent",
                     "raw_text": "交通报销比例为70%"},
                    {"id": "trans_cap", "type": "limit", "title": "交通单次上限",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 500, "unit": "yuan",
                     "raw_text": "交通单次报销不超过500元"},
                    {"id": "trans_approval", "type": "approval", "title": "交通审批阈值",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "超过300元", "value": 300, "unit": "yuan",
                     "raw_text": "交通超过300元需审批"},
                ]
            },
            {
                "id": "office_supplies", "name": "办公用品",
                "rules": [
                    {"id": "office_ratio", "type": "ratio", "title": "办公用品报销比例",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 1.0, "unit": "percent",
                     "raw_text": "办公用品报销比例为100%"},
                    {"id": "office_cap", "type": "limit", "title": "办公用品单次上限",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 1000, "unit": "yuan",
                     "raw_text": "办公用品单次报销不超过1000元"},
                    {"id": "office_approval", "type": "approval", "title": "办公用品审批阈值",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "超过500元", "value": 500, "unit": "yuan",
                     "raw_text": "办公用品超过500元需审批"},
                    {"id": "office_attachment", "type": "requirement", "title": "办公用品需附件",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": None, "unit": "",
                     "raw_text": "办公用品需要附件"},
                ]
            },
            {
                "id": "entertainment", "name": "商务招待",
                "rules": [
                    {"id": "ent_ratio", "type": "ratio", "title": "商务招待报销比例",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 0.5, "unit": "percent",
                     "raw_text": "商务招待报销比例为50%"},
                    {"id": "ent_cap", "type": "limit", "title": "商务招待单次上限",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 1000, "unit": "yuan",
                     "raw_text": "商务招待单次报销不超过1000元"},
                    {"id": "ent_ppl", "type": "limit", "title": "商务招待人均限额",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 200, "unit": "yuan",
                     "raw_text": "商务招待人均不超过200元"},
                    {"id": "ent_approval", "type": "approval", "title": "商务招待审批阈值",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "超过500元", "value": 500, "unit": "yuan",
                     "raw_text": "商务招待超过500元需审批"},
                    {"id": "ent_guest", "type": "requirement", "title": "商务招待需宾客名单",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": None, "unit": "",
                     "raw_text": "商务招待需要宾客名单"},
                ]
            },
        ],
    }

    import json
    with open(os.path.join(settings.policy.policies_dir, "default.json"), "w", encoding="utf-8") as f:
        json.dump(default_policy_json, f, ensure_ascii=False, indent=2)

    # Also create Policy + PolicyVersion in DB for admin UI
    default_policy = Policy(
        name="默认报销政策",
        description="由 seed.py 创建的公司默认报销政策",
        policy_type="expense",
        status=PolicyStatus.PUBLISHED,
        enterprise="default",
        current_version_id=0,  # Will assign after version creation
        created_by=users[0].id,  # admin user
    )
    db.add(default_policy)
    db.flush()

    import datetime
    default_version = PolicyVersion(
        policy_id=default_policy.id,
        version_number=1,
        pdf_filename="seed-default.json",
        pdf_path="",
        pdf_content=json.dumps(default_policy_json, ensure_ascii=False),
        status=PolicyStatus.PUBLISHED,
        ai_draft=None,
        policy_json=default_policy_json,
        created_by=users[0].id,
        published_at=datetime.datetime.utcnow(),
    )
    db.add(default_version)
    db.flush()

    default_policy.current_version_id = default_version.id

    db.commit()
    print("Database seeded successfully!")
    print(f"  Employees: {db.query(Employee).count()}")
    print(f"  Users: {db.query(User).count()}")
    print(f"  Policies: {db.query(Policy).count()}")
    print(f"  Policy file: {settings.policy.policies_dir}/default.json")

finally:
    db.close()
