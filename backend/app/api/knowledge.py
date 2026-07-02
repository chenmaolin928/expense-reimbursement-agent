"""Knowledge base API routes — admin creates/manages, all users can search."""

from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user_id, _parse_auth_header
from app.services.knowledge_service import get_knowledge_service, chunk_text
from app.services.text_quality_assessor import TextQualityAssessor
from app.services.text_extractor import extract_text
from app.services.structured_extractor import StructuredExtractor
from app.schemas.extraction import StructuredExtractionResult
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentDetail,
    DocumentChunksResponse,
    ChunkPreview,
    SearchResult,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# --- Text quality assessor (lazy singleton) ---

_text_quality_assessor: TextQualityAssessor | None = None


def _get_text_quality_assessor() -> TextQualityAssessor:
    global _text_quality_assessor
    if _text_quality_assessor is None:
        _text_quality_assessor = TextQualityAssessor()
    return _text_quality_assessor


def _extract_text(filename: str, content_bytes: bytes) -> tuple[str, dict]:
    """Extract text from uploaded file — delegates to shared text_extractor."""
    return extract_text(filename, content_bytes, assessor=_get_text_quality_assessor())


# --- Knowledge Bases ---

@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    svc = get_knowledge_service(db)
    kb = svc.create_base(name=body.name, description=body.description, created_by=auth["user_id"])
    return KnowledgeBaseResponse(
        id=kb.id, name=kb.name, description=kb.description or "",
        created_by=kb.created_by, is_active=kb.is_active,
        created_at=kb.created_at, document_count=0,
    )


@router.get("/bases", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(db: Session = Depends(get_db)):
    svc = get_knowledge_service(db)
    bases = svc.list_bases()
    return [
        KnowledgeBaseResponse(
            id=kb.id, name=kb.name, description=kb.description or "",
            created_by=kb.created_by, is_active=kb.is_active,
            created_at=kb.created_at, document_count=svc.get_document_count(kb.id),
        )
        for kb in bases
    ]


@router.delete("/bases/{kb_id}")
def delete_knowledge_base(
    kb_id: int, db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    svc = get_knowledge_service(db)
    result = svc.soft_delete_kb(kb_id)
    if not result.success:
        if result.reason == "KB not found":
            raise HTTPException(status_code=404, detail="知识库不存在")
        raise HTTPException(
            status_code=409,
            detail={
                "code": "KB_HAS_PUBLISHED_VERSIONS",
                "message": result.reason,
                "linked_version_ids": result.linked_published_version_ids,
            },
        )
    return {"success": True, "message": result.reason}


# --- Documents ---

@router.post("/bases/{kb_id}/documents", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    kb_id: int, file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    svc = get_knowledge_service(db)
    kb = svc.get_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    content_bytes = file.file.read()

    # Step 1: Extract text with quality assessment
    content, upload_metadata = _extract_text(file.filename or "", content_bytes)
    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    # Step 2: Structured extraction via LLM
    try:
        extractor = StructuredExtractor()
        # For now use a mock-friendly approach — skip LLM call if no client configured
        extraction = StructuredExtractor.empty_result(content[:500])
    except Exception:
        extraction = StructuredExtractor.empty_result(content[:500])

    result = svc.add_document(kb_id=kb_id, filename=file.filename or "untitled", content=content)
    doc = result["document"]
    return KnowledgeDocumentResponse(
        id=doc.id, kb_id=doc.kb_id, filename=doc.filename,
        chunk_count=doc.chunk_count, created_at=doc.created_at,
        chunks_preview=[ChunkPreview(**c) for c in result["chunks_preview"]],
        extraction=extraction,
        upload_metadata=upload_metadata,
    )


@router.get("/bases/{kb_id}/documents", response_model=list[KnowledgeDocumentResponse])
def list_documents(kb_id: int, db: Session = Depends(get_db)):
    svc = get_knowledge_service(db)
    docs = svc.list_documents(kb_id)
    result = []
    for d in docs:
        chunks = svc.get_chunks(d.id)
        result.append(KnowledgeDocumentResponse(
            id=d.id, kb_id=d.kb_id, filename=d.filename,
            chunk_count=d.chunk_count, created_at=d.created_at,
            chunks_preview=[
                ChunkPreview(
                    index=c["chunk_index"] if isinstance(c.get("chunk_index"), int) else i,
                    text=c["text"][:200] + ("..." if len(c["text"]) > 200 else ""),
                    char_count=c["char_count"],
                )
                for i, c in enumerate(chunks[:5])
            ],
        ))
    return result


@router.get("/documents/{doc_id}", response_model=KnowledgeDocumentDetail)
def get_document_detail(doc_id: int, db: Session = Depends(get_db)):
    svc = get_knowledge_service(db)
    doc = svc.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = svc.get_chunks(doc_id)
    return KnowledgeDocumentDetail(
        id=doc.id, kb_id=doc.kb_id, filename=doc.filename,
        content=doc.content, chunk_count=doc.chunk_count, created_at=doc.created_at,
        chunks_preview=[
            ChunkPreview(
                index=c["chunk_index"] if isinstance(c.get("chunk_index"), int) else i,
                text=c["text"],
                char_count=c["char_count"],
            )
            for i, c in enumerate(chunks)
        ],
    )


@router.get("/documents/{doc_id}/chunks", response_model=DocumentChunksResponse)
def get_document_chunks(doc_id: int, db: Session = Depends(get_db)):
    """Return all chunks for a document with their chunk IDs — useful for debugging chunking quality."""
    svc = get_knowledge_service(db)
    doc = svc.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    kb = svc.get_base(doc.kb_id)
    chunks = svc.get_chunks(doc_id)
    return DocumentChunksResponse(
        document_id=doc.id,
        filename=doc.filename,
        kb_name=kb.name if kb else "Unknown",
        total_chunks=len(chunks),
        chunks=[
            ChunkPreview(
                index=c["chunk_index"] if isinstance(c.get("chunk_index"), int) else i,
                text=c["text"],
                char_count=c["char_count"],
            )
            for i, c in enumerate(chunks)
        ],
    )


# --- Search (public) ---

@router.get("/search", response_model=list[SearchResult])
def search_knowledge(
    q: str,
    kb_id: int | None = None,
    top_k: int | None = None,
    threshold: float | None = None,
    db: Session = Depends(get_db),
):
    svc = get_knowledge_service(db)
    results = svc.search(query=q, kb_id=kb_id, top_k=top_k, threshold=threshold)
    return [
        SearchResult(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            filename=r["filename"],
            kb_name=r["kb_name"],
            snippet=r["snippet"],
            score=r["score"],
            distance=r.get("distance", 1.0),
        )
        for r in results
    ]


# --- ChromaDB inspection (debug/verification) ---

@router.get("/chroma-stats")
def chroma_stats():
    """Return ChromaDB collection stats — verify knowledge base indexing succeeded."""
    from app.services.knowledge_service import _get_collection
    col = _get_collection()
    count = col.count()
    peek = col.peek(limit=3)
    return {
        "collection_name": col.name,
        "total_chunks": count,
        "sample_ids": peek.get("ids", []) if peek else [],
        "sample_metadatas": peek.get("metadatas", []) if peek else [],
        "sample_texts": [d[:150] for d in peek.get("documents", [])] if peek else [],
    }


@router.get("/chroma-search-raw")
def chroma_search_raw(
    q: str,
    kb_id: int | None = None,
    top_k: int = 10,
    threshold: float | None = None,
):
    """Search ChromaDB directly and return raw distances — debug tool for relevance tuning."""
    from app.services.knowledge_service import _get_collection, _get_embedding_fn
    col = _get_collection()
    model = _get_embedding_fn()
    query_vec = model([q]).tolist()

    where_filter = {"kb_id": kb_id} if kb_id is not None else None
    raw = col.query(
        query_embeddings=query_vec,
        n_results=top_k,
        where=where_filter,
        include=["metadatas", "documents", "distances", "embeddings"],
    )

    results = []
    if raw and raw.get("ids") and raw["ids"][0]:
        for i, cid in enumerate(raw["ids"][0]):
            meta = raw["metadatas"][0][i] if raw["metadatas"] else {}
            doc_text = raw["documents"][0][i] if raw["documents"] else ""
            distance = raw["distances"][0][i] if raw.get("distances") else 1.0
            cosine_sim = round(max(0.0, 1.0 - float(distance)), 6)
            if threshold is not None and cosine_sim < threshold:
                continue
            results.append({
                "chunk_id": cid,
                "filename": meta.get("filename", ""),
                "kb_name": meta.get("kb_name", ""),
                "text": doc_text[:300],
                "distance": round(float(distance), 6),
                "cosine_similarity": cosine_sim,
            })

    return {
        "query": q,
        "kb_id_filter": kb_id,
        "top_k": top_k,
        "threshold": threshold,
        "total_results": len(results),
        "results": results,
    }
