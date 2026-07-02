"""Chat API — the core Agent endpoint with SSE streaming."""

import json
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import _parse_auth_header
from app.schemas.chat import (
    ChatRequest, ChatMessageResponse, CorrectSearchRequest,
    SessionCreate, SessionResponse, SessionDetail,
)
from app.services.session_service import get_session_service
from app.services.agent_service import run_agent
from app.services.tools import set_tool_context
from app.infrastructure.orm import User, Employee
from app.config import settings

import asyncio

router = APIRouter(prefix="/chat", tags=["chat"])


# ============================================================
# Session CRUD
# ============================================================

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    body: SessionCreate,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    svc = get_session_service(db)
    s = svc.create(user_id=auth["user_id"], title=body.title)
    return SessionResponse(
        id=s.id, title=s.title,
        created_at=s.created_at, updated_at=s.updated_at,
        message_count=0,
    )


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    svc = get_session_service(db)
    sessions = svc.list_by_user(auth["user_id"])
    return [
        SessionResponse(
            id=s.id, title=s.title,
            created_at=s.created_at, updated_at=s.updated_at,
            message_count=svc.count_messages(s.id),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    svc = get_session_service(db)
    s = svc.get(session_id)
    if not s or s.user_id != auth["user_id"]:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = svc.get_messages(session_id)
    return SessionDetail(
        id=s.id, title=s.title,
        created_at=s.created_at, updated_at=s.updated_at,
        message_count=len(messages),
        messages=[
            ChatMessageResponse(
                id=m.id, session_id=m.session_id, role=m.role,
                content=m.content, tool_name=m.tool_name,
                tool_result=m.tool_result, attachments=m.attachments,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    svc = get_session_service(db)
    s = svc.get(session_id)
    if not s or s.user_id != auth["user_id"]:
        raise HTTPException(status_code=404, detail="会话不存在")
    # Also remove session agent on session deletion
    from app.services.session_agent import SessionAgentManager
    SessionAgentManager.remove(session_id)


# ============================================================
# File upload
# ============================================================

@router.post("/sessions/{session_id}/upload")
def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    svc = get_session_service(db)
    s = svc.get(session_id)
    if not s or s.user_id != auth["user_id"]:
        raise HTTPException(status_code=404, detail="会话不存在")

    # Save file with UUID-based name to avoid encoding issues with Chinese filenames
    os.makedirs(settings.storage.invoice_storage_path, exist_ok=True)
    safe_ext = os.path.splitext(file.filename)[1]
    safe_name = f"{session_id}_{uuid.uuid4().hex[:8]}{safe_ext}"
    file_path = os.path.join(settings.storage.invoice_storage_path, safe_name)
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    return {
        "file_path": file_path,
        "filename": safe_name,
        "original_filename": file.filename,
        "url": f"/api/v1/files/{safe_name}",
    }


# ============================================================
# Correct & Re-search — user fixes OCR fields, re-runs policy search only
# ============================================================

@router.post("/sessions/{session_id}/correct-search")
def correct_search(
    session_id: str,
    req: CorrectSearchRequest,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    """User corrected invoice fields → re-run knowledge search without re-OCR."""
    svc = get_session_service(db)
    s = svc.get(session_id)
    if not s or s.user_id != auth["user_id"]:
        raise HTTPException(status_code=404, detail="会话不存在")

    # Build corrected invoice context
    corrected = dict(req.corrected_fields)

    # Save user correction message
    svc.add_message(
        session_id=session_id,
        role="user",
        content=f"[修正信息] {json.dumps(corrected, ensure_ascii=False)}",
    )

    # Re-run knowledge search with corrected fields
    from app.services.knowledge_service import KnowledgeService
    from app.services.policy_card_service import build_policy_card
    from app.services.agent_service import _synthesize_policy_judgment
    from app.services.policy_repository import PolicyRepository
    from app.engines.policy_engine import PolicyEngine
    from app.engines.calculator_engine import CalculatorEngine
    from app.engines.rule_engine import RuleEngine
    from app.services.policy_storage_backends import DatabaseBackend
    from app.database import SessionLocal

    # Build search query from corrected fields
    query_parts = []
    if "category" in corrected:
        query_parts.append(str(corrected["category"]))
    if "vendor" in corrected:
        query_parts.append(str(corrected["vendor"]))
    query = " ".join(query_parts) if query_parts else "报销标准"

    ks = KnowledgeService(db)
    raw_results = ks.search(query)
    search_results = {
        "total_results": len(raw_results),
        "results": [
            {
                "chunk_id": r["chunk_id"],
                "snippet": r["snippet"],
                "kb_name": r["kb_name"],
                "filename": r["filename"],
                "score": r["score"],
            }
            for r in raw_results[:5]
        ],
    }

    # Build invoice-like result from corrected fields for judgment
    invoice_result = {
        "vendor": corrected.get("vendor", ""),
        "amount": corrected.get("amount", 0),
        "date": corrected.get("date", ""),
        "category_raw": corrected.get("category", "other"),
        "file_path": req.invoice_path,
    }

    repo = PolicyRepository(DatabaseBackend(SessionLocal))
    policy_engine = PolicyEngine(repo)
    calculator_engine = CalculatorEngine(policy_engine)
    rule_engine = RuleEngine(policy_engine)
    judgment = _synthesize_policy_judgment(
        invoice_result,
        search_results,
        calculator=calculator_engine,
        rule_engine=rule_engine,
    )
    card = build_policy_card(search_results, judgment)

    return card["data"]


# ============================================================
# Agent Chat (SSE Streaming) — THE CORE ENDPOINT
# ============================================================

@router.post("")
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    """Send a message to the AI Agent. Returns Server-Sent Events (SSE).

    Event types: thinking, tool_call, tool_result, message, confirm, done
    """
    svc = get_session_service(db)

    # Validate session
    session = svc.get(req.session_id)
    if not session or session.user_id != auth["user_id"]:
        raise HTTPException(status_code=404, detail="会话不存在")

    # Get user/employee info (stays LOCAL, never sent to LLM)
    user = db.query(User).filter(User.id == auth["user_id"]).first()
    employee = None
    emp_id = None
    email = None
    if user and user.employee_id:
        employee = db.query(Employee).filter(Employee.id == user.employee_id).first()
        if employee:
            emp_id = employee.id
            email = employee.email

    # Save user message
    user_msg = svc.add_message(
        session_id=req.session_id, role="user", content=req.message,
        attachments=req.attachments if req.attachments else None,
    )

    # ---- LLM Security Gateway ----
    from app.services.llm_security_gateway import LLMSecurityGateway
    gateway = LLMSecurityGateway(db, req.session_id)

    # ---- Engines (Cloud Brain, Local Hands) ----
    from app.services.policy_repository import PolicyRepository
    from app.engines.policy_engine import PolicyEngine
    from app.engines.calculator_engine import CalculatorEngine
    from app.engines.rule_engine import RuleEngine
    from app.services.policy_storage_backends import DatabaseBackend
    from app.database import SessionLocal

    repo = PolicyRepository(DatabaseBackend(SessionLocal))
    policy_engine = PolicyEngine(repo)
    calculator_engine = CalculatorEngine(policy_engine)
    rule_engine = RuleEngine(policy_engine)

    # 用户消息：原文存 DB 供前端展示，清洗版送 LLM
    clean_message = gateway.build_user_message(req.message)
    gateway.audit_log("user_message", {"raw_len": len(req.message), "clean_len": len(clean_message)})

    # Build message history from DB
    history = []
    for m in svc.get_messages(req.session_id)[:-1]:  # exclude the one we just saved
        history.append({"role": m.role, "content": m.content})

    # Build full message with attachment markers
    full_message = clean_message
    if req.attachments:
        full_message = f"[已上传文件: {', '.join(req.attachments)}]\n{clean_message}"

    async def event_stream():
        try:
            # Clean up idle sessions periodically (1/10 chance)
            import random
            if random.random() < 0.1:
                from app.services.session_agent import SessionAgentManager
                removed = SessionAgentManager.cleanup()
                if removed:
                    import logging
                    logging.getLogger(__name__).info(f"Cleaned up {removed} idle session agents")

            events = await run_agent(
                session_id=req.session_id,
                user_message=full_message,
                user_id=auth["user_id"],
                employee_id=emp_id,
                user_email=email,
                message_history=history,
                security_gateway=gateway,
                policy_engine=policy_engine,
                calculator_engine=calculator_engine,
                rule_engine=rule_engine,
            )

            assistant_content = ""
            for event in events:
                # Accumulate assistant messages for DB persistence
                if event["type"] == "message" and event.get("role") == "assistant":
                    assistant_content += event.get("content", "")
                elif event["type"] == "message" and event.get("role") == "user":
                    continue  # Already saved
                elif event["type"] == "tool_call":
                    # Log tool call
                    svc.add_message(
                        session_id=req.session_id,
                        role="tool",
                        content=None,
                        tool_name=event["tool"],
                        tool_result={"args": event.get("args", {})},
                    )
                elif event["type"] == "tool_result":
                    svc.add_message(
                        session_id=req.session_id,
                        role="tool",
                        content=None,
                        tool_name=event["tool"],
                        tool_result=event.get("result", {}),
                    )

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # Save assistant message
            if assistant_content:
                svc.add_message(
                    session_id=req.session_id,
                    role="assistant",
                    content=assistant_content,
                )

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
