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
def client(monkeypatch):
    """FastAPI test client with an explicit test-only mock LLM.

    Runtime code no longer auto-falls back to mock mode, so tests inject a
    deterministic fake model explicitly to avoid network dependence.
    """
    from app.infrastructure.llm_client import _MockChatModel
    from app.services.session_agent import SessionAgentManager
    import app.infrastructure.llm_client as llm_client
    import app.services.agent_service as agent_service
    import app.services.session_agent as session_agent

    def build_test_model():
        return _MockChatModel()

    monkeypatch.setattr(llm_client, "_model", None)
    monkeypatch.setattr(llm_client, "get_model", build_test_model)
    monkeypatch.setattr(agent_service, "get_model", build_test_model)
    monkeypatch.setattr(session_agent, "get_model", build_test_model)
    SessionAgentManager._instances.clear()

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
