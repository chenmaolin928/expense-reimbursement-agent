"""Knowledge base API routes — admin creates/manages, all users can search."""

from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user_id, _parse_auth_header
from app.services.knowledge_service import get_knowledge_service
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentDetail,
    SearchResult,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _extract_text(filename: str, content_bytes: bytes) -> str:
    """Extract text from uploaded file. Supports PDF, Word, and plain text (UTF-8/GBK)."""
    lower = filename.lower()

    # PDF: extract with PyPDF2
    if lower.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(content_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
            if text:
                return text
        except Exception:
            pass  # fall through to text decode

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
            pass  # fall through to text decode

    # Plain text: try UTF-8, then GBK
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return content_bytes.decode("gbk")
    except Exception:
        pass

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
    doc = svc.add_document(kb_id=kb_id, filename=file.filename or "untitled", content=content)
    return KnowledgeDocumentResponse(
        id=doc.id, kb_id=doc.kb_id, filename=doc.filename,
        chunk_count=doc.chunk_count, created_at=doc.created_at,
    )


@router.get("/bases/{kb_id}/documents", response_model=list[KnowledgeDocumentResponse])
def list_documents(kb_id: int, db: Session = Depends(get_db)):
    svc = get_knowledge_service(db)
    docs = svc.list_documents(kb_id)
    return [
        KnowledgeDocumentResponse(
            id=d.id, kb_id=d.kb_id, filename=d.filename,
            chunk_count=d.chunk_count, created_at=d.created_at,
        )
        for d in docs
    ]


@router.get("/documents/{doc_id}", response_model=KnowledgeDocumentDetail)
def get_document_detail(doc_id: int, db: Session = Depends(get_db)):
    svc = get_knowledge_service(db)
    doc = svc.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return KnowledgeDocumentDetail(
        id=doc.id, kb_id=doc.kb_id, filename=doc.filename,
        content=doc.content, chunk_count=doc.chunk_count, created_at=doc.created_at,
    )


# --- Search (public) ---

@router.get("/search", response_model=list[SearchResult])
def search_knowledge(q: str, kb_id: int | None = None, db: Session = Depends(get_db)):
    svc = get_knowledge_service(db)
    results = svc.search(query=q, kb_id=kb_id)
    return [
        SearchResult(
            document_id=r["document_id"], filename=r["filename"],
            kb_name=r["kb_name"], snippet=r["snippet"], score=r["score"],
        )
        for r in results
    ]
