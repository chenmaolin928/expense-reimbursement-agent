"""Chat & SSE event schemas."""

from pydantic import BaseModel
from datetime import datetime


class ChatRequest(BaseModel):
    session_id: str
    message: str
    attachments: list[str] = []  # file paths from prior uploads


class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    role: str  # user, assistant, tool
    content: str | None = None
    tool_name: str | None = None
    tool_result: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    title: str = "New Chat"


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class SessionDetail(SessionResponse):
    messages: list[ChatMessageResponse] = []
