"""Knowledge base service — CRUD + text search (keyword-based, RAG-ready)."""

from sqlalchemy.orm import Session
from app.infrastructure.orm import KnowledgeBase, KnowledgeDocument


class KnowledgeService:
    """Manages knowledge bases and documents. Simple keyword search for now."""

    def __init__(self, db: Session):
        self.db = db

    # --- Knowledge Base CRUD ---

    def create_base(self, name: str, description: str, created_by: int) -> KnowledgeBase:
        kb = KnowledgeBase(name=name, description=description, created_by=created_by)
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def list_bases(self, only_active: bool = True):
        q = self.db.query(KnowledgeBase)
        if only_active:
            q = q.filter(KnowledgeBase.is_active == True)
        return q.order_by(KnowledgeBase.created_at.desc()).all()

    def get_base(self, kb_id: int) -> KnowledgeBase | None:
        return self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()

    def delete_base(self, kb_id: int) -> bool:
        kb = self.get_base(kb_id)
        if not kb:
            return False
        kb.is_active = False
        self.db.commit()
        return True

    # --- Document CRUD ---

    def add_document(self, kb_id: int, filename: str, content: str) -> KnowledgeDocument:
        doc = KnowledgeDocument(
            kb_id=kb_id,
            filename=filename,
            content=content,
            chunk_count=1,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def list_documents(self, kb_id: int):
        return (
            self.db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.kb_id == kb_id)
            .order_by(KnowledgeDocument.created_at.desc())
            .all()
        )

    def get_document(self, doc_id: int) -> KnowledgeDocument | None:
        return self.db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()

    def get_document_count(self, kb_id: int) -> int:
        return self.db.query(KnowledgeDocument).filter(KnowledgeDocument.kb_id == kb_id).count()

    # --- Search ---

    def search(self, query: str, kb_id: int | None = None) -> list[dict]:
        """Simple keyword search across documents. RAG-ready — swap with embeddings later."""
        q = self.db.query(KnowledgeDocument).join(
            KnowledgeBase, KnowledgeDocument.kb_id == KnowledgeBase.id
        ).filter(KnowledgeBase.is_active == True)

        if kb_id:
            q = q.filter(KnowledgeDocument.kb_id == kb_id)

        docs = q.all()
        results = []
        for doc in docs:
            if query.lower() in doc.content.lower():
                # Extract a snippet around the match
                idx = doc.content.lower().find(query.lower())
                start = max(0, idx - 50)
                end = min(len(doc.content), idx + len(query) + 80)
                snippet = doc.content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(doc.content):
                    snippet = snippet + "..."

                results.append({
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "kb_name": doc.knowledge_base.name,
                    "snippet": snippet,
                    "score": 0.9,  # simulated score
                })
        return results


def get_knowledge_service(db: Session) -> KnowledgeService:
    return KnowledgeService(db)
