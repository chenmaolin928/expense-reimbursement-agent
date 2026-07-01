"""Knowledge base API routes — admin creates/manages, all users can search."""

from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user_id, _parse_auth_header
from app.services.knowledge_service import get_knowledge_service, chunk_text
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


def _is_garbled(text: str) -> bool:
    """Heuristic: text is likely garbled if it has high-byte chars but no CJK characters.

    Garbled Chinese text decoded with wrong encoding typically produces strings like
    'R\\x1be°yÑb\\x80g' — high-byte chars (>127) present but no valid CJK (U+4E00–U+9FFF).

    Legitimate Western text with accented characters (é, ñ, ü) has only a few high-bytes
    — we require either >5 high-byte chars OR >30% high-byte density to avoid false positives.
    """
    if not text.strip():
        return True
    total = len(text)
    high_byte = sum(1 for c in text if ord(c) > 127)
    cjk = sum(1 for c in text if '一' <= c <= '鿿')
    if cjk > 0:
        return False
    # No CJK at all but significant high-byte density → garbled
    return high_byte > 5 or (high_byte > 0 and high_byte / max(total, 1) > 0.3)


def _extract_text(filename: str, content_bytes: bytes) -> str:
    """Extract text from uploaded file. Supports PDF, Word, and plain text (auto-detect encoding).

    PDF extraction: tries pdfplumber first (proper Chinese CMap support),
    falls back to PyPDF2 for simple PDFs.
    """
    lower = filename.lower()

    # PDF: try pdfplumber first (best CJK support), then PyPDF2
    if lower.endswith(".pdf"):
        # --- pdfplumber (primary) ---
        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(BytesIO(content_bytes)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages).strip()
            if text and not _is_garbled(text):
                return text
        except Exception:
            pass

        # --- PyPDF2 (fallback) ---
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(content_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
            if text and not _is_garbled(text):
                return text
        except Exception:
            pass

        # Both methods failed or produced garbled text
        if text:
            raise HTTPException(
                status_code=400,
                detail="PDF 文本提取失败（可能是扫描件或加密 PDF），请上传可搜索文本的 PDF 或手动粘贴内容",
            )
        raise HTTPException(status_code=400, detail="无法从 PDF 中提取文本内容")

    # Word .docx: extract with python-docx
    if lower.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(BytesIO(content_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs).strip()
            if text:
                return text
        except Exception:
            pass

    # Plain text: detect encoding with chardet, fallback to UTF-8 → GBK
    import chardet
    detected = chardet.detect(content_bytes)
    encoding = detected.get("encoding") or "utf-8"
    confidence = detected.get("confidence", 0)

    # chardet can misdetect GBK as ISO-8859-1 / Windows-1252 (which decode every byte
    # without error, producing garbled text). If confidence is low or the detected
    # encoding is a single-byte charset, try Chinese encodings first.
    single_byte_encodings = {"iso-8859-1", "iso-8859-2", "iso-8859-5", "iso-8859-9",
                             "windows-1252", "windows-1250", "windows-1251", "windows-1254",
                             "mac_roman", "latin-1", "latin1", "tis-620",}
    if confidence < 0.6 or encoding.lower() in single_byte_encodings:
        # Try Chinese encodings first for high-confidence detection
        for fb in ("gb18030", "gbk", "gb2312", "utf-8"):
            try:
                decoded = content_bytes.decode(fb)
                if not _is_garbled(decoded):
                    return decoded
            except (UnicodeDecodeError, LookupError):
                continue

    # Try the detected encoding
    try:
        decoded = content_bytes.decode(encoding)
        if not _is_garbled(decoded):
            return decoded
    except (UnicodeDecodeError, LookupError):
        pass

    # Last resort: try common Chinese encodings
    for fallback in ("utf-8", "gbk", "gb2312", "gb18030"):
        try:
            decoded = content_bytes.decode(fallback)
            if not _is_garbled(decoded):
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue

    raise HTTPException(status_code=400, detail="无法解析文件内容，请上传 UTF-8/GBK 文本文件、PDF 或 Word 文档")


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


@router.delete("/bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: int, db: Session = Depends(get_db),
    auth: dict = Depends(_parse_auth_header),
):
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    svc = get_knowledge_service(db)
    if not svc.delete_base(kb_id):
        raise HTTPException(status_code=404, detail="知识库不存在")
    return None


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
    content = _extract_text(file.filename or "", content_bytes)
    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")
    result = svc.add_document(kb_id=kb_id, filename=file.filename or "untitled", content=content)
    doc = result["document"]
    return KnowledgeDocumentResponse(
        id=doc.id, kb_id=doc.kb_id, filename=doc.filename,
        chunk_count=doc.chunk_count, created_at=doc.created_at,
        chunks_preview=[ChunkPreview(**c) for c in result["chunks_preview"]],
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
    # Peek a few entries to show what's actually stored
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
