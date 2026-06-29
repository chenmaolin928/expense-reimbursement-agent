"""Knowledge base DTOs."""

from pydantic import BaseModel, Field
from datetime import datetime


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str
    created_by: int
    is_active: bool
    created_at: datetime
    document_count: int = 0

    class Config:
        from_attributes = True


class KnowledgeDocumentResponse(BaseModel):
    id: int
    kb_id: int
    filename: str
    chunk_count: int
    created_at: datetime
    # Content is NOT returned in lists — only in detail


class KnowledgeDocumentDetail(BaseModel):
    id: int
    kb_id: int
    filename: str
    content: str
    chunk_count: int
    created_at: datetime


class SearchResult(BaseModel):
    document_id: int
    filename: str
    kb_name: str
    snippet: str
    score: float = 1.0
