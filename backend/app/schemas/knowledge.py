"""Knowledge base DTOs."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.schemas.extraction import StructuredExtractionResult


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


class ChunkPreview(BaseModel):
    index: int
    text: str
    char_count: int


class KnowledgeDocumentResponse(BaseModel):
    id: int
    kb_id: int
    filename: str
    chunk_count: int
    created_at: datetime
    chunks_preview: list[ChunkPreview] = []
    extraction: Optional[StructuredExtractionResult] = None
    upload_metadata: Optional[dict[str, Any]] = None


class KnowledgeDocumentDetail(BaseModel):
    id: int
    kb_id: int
    filename: str
    content: str
    chunk_count: int
    created_at: datetime
    chunks_preview: list[ChunkPreview] = []  # all chunks
    extraction: Optional[StructuredExtractionResult] = None


class DocumentChunksResponse(BaseModel):
    document_id: int
    filename: str
    kb_name: str
    total_chunks: int
    chunks: list[ChunkPreview]


class SearchResult(BaseModel):
    chunk_id: str
    document_id: int
    filename: str
    kb_name: str
    snippet: str
    score: float = 1.0
    distance: float | None = None
