"""Chat session service — CRUD for conversations."""

from sqlalchemy.orm import Session
from app.infrastructure.orm import ChatSession, ChatMessage


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, title: str = "New Chat") -> ChatSession:
        s = ChatSession(user_id=user_id, title=title)
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def list_by_user(self, user_id: int):
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == user_id, ChatSession.is_active == True)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def get(self, session_id: str) -> ChatSession | None:
        return self.db.query(ChatSession).filter(ChatSession.id == session_id).first()

    def get_messages(self, session_id: str):
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_name: str | None = None,
        tool_result: dict | None = None,
        attachments: list[str] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_result=tool_result,
            attachments=attachments,
        )
        self.db.add(msg)
        # Touch session updated_at
        session = self.get(session_id)
        if session:
            from datetime import datetime
            session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def delete(self, session_id: str) -> bool:
        s = self.get(session_id)
        if not s:
            return False
        s.is_active = False
        self.db.commit()
        return True

    def count_messages(self, session_id: str) -> int:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .count()
        )


def get_session_service(db: Session) -> SessionService:
    return SessionService(db)
