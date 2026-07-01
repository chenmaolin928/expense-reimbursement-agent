"""Test fixtures — shared across all test modules."""

import os
import sys
import pytest

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.database import engine, Base, SessionLocal
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    """Create tables fresh before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Raw database session for service-level tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_token(client):
    """Get admin auth token."""
    # Seed admin user first
    from app.infrastructure.orm import Employee, User
    from app.domain.enums import UserRole
    import hashlib

    db = SessionLocal()
    try:
        emp = Employee(
            employee_code="EMP-TEST-01",
            full_name="Test Admin",
            email="admin@test.cn",
            department="IT",
            bank_account="0000",
        )
        db.add(emp)
        db.flush()

        salt = "expense-agent-salt-v1"
        pw = hashlib.sha256(f"{salt}:admin123".encode()).hexdigest()
        user = User(username="admin", password_hash=pw, role=UserRole.ADMIN, employee_id=emp.id)
        db.add(user)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    return resp.json()["token"]


@pytest.fixture
def employee_token(client, admin_token):
    """Get employee auth token."""
    from app.infrastructure.orm import Employee, User
    from app.domain.enums import UserRole
    import hashlib

    db = SessionLocal()
    try:
        emp = Employee(
            employee_code="EMP-TEST-02",
            full_name="Zhang Wei",
            email="zhangwei@test.cn",
            department="Engineering",
            bank_account="1111",
        )
        db.add(emp)
        db.flush()

        salt = "expense-agent-salt-v1"
        pw = hashlib.sha256(f"{salt}:zhang123".encode()).hexdigest()
        user = User(username="zhangwei", password_hash=pw, role=UserRole.EMPLOYEE, employee_id=emp.id)
        db.add(user)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/auth/login", json={"username": "zhangwei", "password": "zhang123"})
    return resp.json()["token"]
