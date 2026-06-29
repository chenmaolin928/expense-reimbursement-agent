"""SQLAlchemy ORM models for all 9 tables."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, Date,
    ForeignKey, JSON, Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.domain.enums import (
    UserRole, ReportStatus, ExpenseCategory,
    DecisionStatus, ExecutionStatus, NotificationEvent,
)


def _gen_uuid() -> str:
    return uuid.uuid4().hex[:12]


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_code = Column(String(20), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)         # SENSITIVE
    email = Column(String(150), nullable=False)              # SENSITIVE
    department = Column(String(80), nullable=False)          # SENSITIVE
    bank_account = Column(String(40), nullable=False)        # SENSITIVE (simulated)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("Employee", remote_side=[id], backref="subordinates")
    user = relationship("User", back_populates="employee", uselist=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee", back_populates="user")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(32), primary_key=True, default=_gen_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), default="New Chat")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, tool
    content = Column(Text, nullable=True)
    tool_calls = Column(JSON, nullable=True)       # LLM-requested function calls
    tool_name = Column(String(100), nullable=True)  # which tool was called
    tool_result = Column(JSON, nullable=True)       # tool execution result
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("KnowledgeDocument", back_populates="knowledge_base")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    chunk_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")


class ExpenseReport(Base):
    __tablename__ = "expense_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_number = Column(String(30), unique=True, nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    session_id = Column(String(32), ForeignKey("chat_sessions.id"), nullable=True)
    total_amount = Column(Float, default=0.0)
    status = Column(SAEnum(ReportStatus), nullable=False, default=ReportStatus.DRAFT)
    cloud_decision_id = Column(String(64), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("expense_reports.id"), nullable=False)
    invoice_filename = Column(String(255), nullable=True)
    invoice_path = Column(String(500), nullable=True)
    ocr_vendor = Column(String(200), nullable=True)
    ocr_amount = Column(Float, nullable=True)
    ocr_date = Column(Date, nullable=True)
    ocr_category_raw = Column(String(100), nullable=True)
    ocr_items = Column(JSON, nullable=True)
    desensitized_batch_id = Column(String(64), nullable=True)
    cloud_decision_status = Column(String(30), nullable=True)
    cloud_decision_category = Column(String(50), nullable=True)
    cloud_approved_amount = Column(Float, nullable=True)
    cloud_decision_raw = Column(JSON, nullable=True)  # Full cloud response (audit)
    execution_status = Column(SAEnum(ExecutionStatus), nullable=False, default=ExecutionStatus.PENDING_OCR)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PiiMapping(Base):
    __tablename__ = "pii_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(30), nullable=False)   # employee_name, employee_id, department, email
    real_value = Column(Text, nullable=False)            # SENSITIVE — actual PII value
    token = Column(String(64), unique=True, nullable=False)  # ENT-xxx
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("expense_reports.id"), nullable=True)
    recipient_email = Column(String(150), nullable=False)
    event_type = Column(String(30), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    is_sent = Column(Boolean, default=True)  # always True in simulation


class StatusTransition(Base):
    __tablename__ = "status_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("expense_reports.id"), nullable=False)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    triggered_by = Column(String(30), nullable=False)  # system, employee, manager, cloud_agent
    actor_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
