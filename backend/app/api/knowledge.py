"""Knowledge base API routes — admin creates/manages, all users can search."""

from io import BytesIO
import unicodedata
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

# --- Supported file types ---

# Mapping: extension → extraction strategy
# - "ocr":  OCR-based extraction (rendered page images → EasyOCR)
_SUPPORTED_EXTENSIONS: dict[str, list[str]] = {
    ".txt":  ["text"],
    ".docx": ["text"],
    ".pdf":  ["ocr"],  # OCR only — text layer extraction causes CJK mojibake
}


def _get_extraction_strategies(filename: str) -> list[str]:
    """Return the ordered list of extraction strategies based on file extension."""
    lower = filename.lower()
    for ext, strategies in _SUPPORTED_EXTENSIONS.items():
        if lower.endswith(ext):
            return strategies
    raise HTTPException(
        status_code=400,
        detail=f"不支持的文件类型: {filename}。支持的类型: .txt, .docx, .pdf",
    )


def _is_garbled(text: str) -> bool:
    """Heuristic: text is likely garbled if it has high-byte chars but no CJK characters.

    Garbled Chinese text decoded with wrong encoding typically produces strings like
    'R\\x1be°yÑb\\x80g' — high-byte chars (>127) present but no valid CJK (U+4E00–U+9FFF).

    Legitimate Western text with accented characters (é, ñ, ü) has only a few high-bytes
    — we require either >5 high-byte chars OR >30% high-byte density to avoid false positives.
    """
    stripped = text.strip()
    if not stripped:
        return True

    visible_chars = [c for c in stripped if not c.isspace()]
    if not visible_chars:
        return True

    total = len(visible_chars)
    high_byte = sum(1 for c in visible_chars if ord(c) > 127)
    cjk = sum(1 for c in visible_chars if "一" <= c <= "鿿")
    control_chars = sum(
        1
        for c in visible_chars
        if unicodedata.category(c).startswith("C") and c not in "\n\r\t\f"
    )
    replacement_chars = stripped.count("\ufffd")

    # PDF mojibake often contains null bytes or other control characters mixed with ASCII.
    if control_chars > 0 or replacement_chars > 0:
        return True

    # A single accidental CJK codepoint inside symbol soup should not whitelist the whole text.
    cjk_ratio = cjk / total
    if cjk_ratio >= 0.2:
        return False

    if cjk > 0:
        return high_byte > 5 or (high_byte > 0 and high_byte / total > 0.3)

    # No CJK at all but significant high-byte density → garbled
    return high_byte > 5 or (high_byte > 0 and high_byte / max(total, 1) > 0.3)


def _extract_text(filename: str, content_bytes: bytes) -> str:
    """Extract text from uploaded file based on its extension.

    Dispatch logic (declared in _SUPPORTED_EXTENSIONS):
      .txt  → text (chardet encoding detection)
      .docx → text (python-docx)
      .pdf  → ocr (PyMuPDF page rendering → EasyOCR)
    """
    strategies = _get_extraction_strategies(filename)

    for strategy in strategies:
        if strategy == "text":
            result = _extract_text_layer(filename, content_bytes)
        elif strategy == "ocr":
            result = _ocr_extract(filename, content_bytes)
        else:
            continue

        if result and not _is_garbled(result):
            return result

    # All strategies exhausted
    raise HTTPException(status_code=400, detail="无法从文件中提取文本内容")


def _extract_text_layer(filename: str, content_bytes: bytes) -> str | None:
    """Extract text from text-based files (PDF text layer, DOCX, TXT). Returns None if extraction fails."""
    lower = filename.lower()

    # Word .docx: extract with python-docx
    if lower.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(BytesIO(content_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs).strip()
            return text if text else None
        except Exception:
            return None

    # Plain text: detect encoding with chardet
    import chardet
    detected = chardet.detect(content_bytes)
    encoding = detected.get("encoding") or "utf-8"
    confidence = detected.get("confidence", 0)

    single_byte_encodings = {"iso-8859-1", "iso-8859-2", "iso-8859-5", "iso-8859-9",
                             "windows-1252", "windows-1250", "windows-1251", "windows-1254",
                             "mac_roman", "latin-1", "latin1", "tis-620"}

    # Low confidence or single-byte charset → try Chinese encodings first
    if confidence < 0.6 or encoding.lower() in single_byte_encodings:
        for fb in ("gb18030", "gbk", "gb2312", "utf-8"):
            try:
                decoded = content_bytes.decode(fb)
                if not _is_garbled(decoded):
                    return decoded
            except (UnicodeDecodeError, LookupError):
                continue

    try:
        decoded = content_bytes.decode(encoding)
        if not _is_garbled(decoded):
            return decoded
    except (UnicodeDecodeError, LookupError):
        pass

    for fallback in ("utf-8", "gbk", "gb2312", "gb18030"):
        try:
            decoded = content_bytes.decode(fallback)
            if not _is_garbled(decoded):
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue

    return None


# --- Lazy OCR reader singleton ---
# Creating an EasyOCR reader is expensive (~2-5s model load, ~100MB+ memory).
# Re-creating it on every PDF upload freezes the request. Cache it at module level.

_ocr_reader = None


def _get_ocr_reader():
    """Return the cached EasyOCR reader, creating it on first call."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
    return _ocr_reader


def _ocr_extract(filename: str, content_bytes: bytes) -> str | None:
    """Extract text from image-based files via OCR. Currently supports PDF → page images → EasyOCR."""
    lower = filename.lower()

    if lower.endswith(".pdf"):
        try:
            import fitz  # PyMuPDF
            import numpy as np

            reader = _get_ocr_reader()
            doc = fitz.open(stream=content_bytes, filetype="pdf")
            pages_text: list[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )
                results = reader.readtext(img_array, detail=0)
                page_text = "\n".join(results)
                pages_text.append(page_text)
            doc.close()

            text = "\n".join(pages_text).strip()
            return text if text and not _is_garbled(text) else None
        except Exception:
            pass

    return None


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
