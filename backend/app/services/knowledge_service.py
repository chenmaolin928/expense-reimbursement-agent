"""Knowledge base service — ChromaDB semantic search with sentence-transformers.

Chunk ID format: kb-{kb_id}-doc-{doc_id}-chunk-{idx:04d}
This enables precise deletion by knowledge base or document, then re-indexing.

Architecture:
  SQLite: knowledge_bases + knowledge_documents (metadata, full content)
  ChromaDB: knowledge_chunks collection (384d vectors + metadata)
"""

import os
import logging
from sqlalchemy.orm import Session
from app.infrastructure.orm import KnowledgeBase, KnowledgeDocument
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> list[str]:
    """Split text into overlapping chunks for indexing.

    Strategy: split by double-newline (paragraph) first, then split long paragraphs
    by sentence boundaries when they exceed chunk_size.
    """
    chunk_size = chunk_size or settings.kb.chunk_size
    chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.kb.chunk_overlap

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []

    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
            continue
        sentences = _split_sentences(para)
        current = ""
        for s in sentences:
            if len(current) + len(s) <= chunk_size:
                current += s
            else:
                if current.strip():
                    chunks.append(current.strip())
                if chunk_overlap > 0 and len(current) > chunk_overlap:
                    current = current[-chunk_overlap:] + s
                else:
                    current = s
        if current.strip():
            chunks.append(current.strip())

    return chunks if chunks else [text]


def _split_sentences(text: str) -> list[str]:
    """Split text at Chinese/English sentence boundaries, keeping the delimiter."""
    import re
    parts = re.split(r"(?<=[。！？.!?])", text)
    return [p for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Chunk ID helpers
# ---------------------------------------------------------------------------

def make_chunk_id(kb_id: int, doc_id: int, chunk_index: int) -> str:
    return f"kb-{kb_id}-doc-{doc_id}-chunk-{chunk_index:04d}"


def make_doc_filter(doc_id: int) -> dict:
    """ChromaDB where filter to match all chunks from a document."""
    return {"doc_id": doc_id}


def make_kb_filter(kb_id: int) -> dict:
    """ChromaDB where filter to match all chunks from a knowledge base."""
    return {"kb_id": kb_id}


# ---------------------------------------------------------------------------
# Embedding model (lazy singleton)
# ---------------------------------------------------------------------------

_embedding_model = None


def _get_embedding_fn():
    """Return a callable that embeds text → 384d vectors."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {settings.kb.embedding_model}")
        _embedding_model = SentenceTransformer(settings.kb.embedding_model)
    return _embedding_model.encode


# ---------------------------------------------------------------------------
# ChromaDB client (lazy singleton)
# ---------------------------------------------------------------------------

_chroma_client = None
_collection = None


def _get_collection():
    """Get or create the knowledge_chunks ChromaDB collection."""
    global _chroma_client, _collection
    if _collection is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        os.makedirs(settings.kb.chroma_path, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=settings.kb.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name="knowledge_chunks",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _invalidate_collection():
    """Force re-init (for testing)."""
    global _chroma_client, _collection
    _chroma_client = None
    _collection = None


# ---------------------------------------------------------------------------
# Knowledge Service
# ---------------------------------------------------------------------------

class KnowledgeService:
    """Manages knowledge bases and documents with ChromaDB semantic search."""

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
        # Remove all chunks from ChromaDB
        self._delete_chunks_by_kb(kb_id)
        return True

    # --- Document CRUD ---

    def add_document(self, kb_id: int, filename: str, content: str) -> dict:
        """Add a document, chunk it, embed chunks, store in ChromaDB + SQLite."""
        chunks = chunk_text(content)
        doc = KnowledgeDocument(
            kb_id=kb_id,
            filename=filename,
            content=content,
            chunk_count=len(chunks),
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        # Index into ChromaDB
        self._index_chunks(doc, chunks)

        # Return with chunk previews
        preview = _make_chunk_previews(chunks)
        return {"document": doc, "chunks_preview": preview}

    def update_document(self, doc_id: int, content: str) -> dict | None:
        """Update a document: delete old chunks, re-chunk, re-index.

        This is the "先删后增" pattern — safe, idempotent, no cross-document impact.
        """
        doc = self.db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
        if not doc:
            return None

        # 1. Delete old chunks from ChromaDB
        self._delete_chunks_by_doc(doc_id)

        # 2. Re-chunk new content
        chunks = chunk_text(content)

        # 3. Re-index into ChromaDB
        self._index_chunks(doc, chunks)

        # 4. Update SQLite
        doc.content = content
        doc.chunk_count = len(chunks)
        self.db.commit()
        self.db.refresh(doc)

        preview = _make_chunk_previews(chunks)
        return {"document": doc, "chunks_preview": preview}

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

    def get_chunks(self, doc_id: int) -> list[dict]:
        """Return all chunk texts + metadata for a document."""
        col = _get_collection()
        try:
            result = col.get(where=make_doc_filter(doc_id))
        except Exception:
            return []
        items = []
        if result and result["ids"]:
            metadatas = result["metadatas"] or []
            documents = result["documents"] or []
            for i, cid in enumerate(result["ids"]):
                items.append({
                    "chunk_id": cid,
                    "text": documents[i] if i < len(documents) else "",
                    "chunk_index": metadatas[i].get("chunk_index", i) if i < len(metadatas) else i,
                    "char_count": len(documents[i]) if i < len(documents) else 0,
                })
            items.sort(key=lambda x: x["chunk_index"])
        return items

    # --- Search ---

    def search(self, query: str, kb_id: int | None = None, top_k: int | None = None, threshold: float | None = None) -> list[dict]:
        """Semantic search via ChromaDB. Returns results above threshold sorted by score desc."""
        col = _get_collection()
        n_results = top_k or settings.kb.top_k
        min_score = threshold if threshold is not None else 0.0

        # Fast bail-out: if collection is empty, don't bother embedding
        if col.count() == 0:
            logger.warning(f"[search] ChromaDB collection is empty, returning no results for query='{query[:80]}'")
            return []

        model = _get_embedding_fn()
        query_vec = model([query]).tolist()

        where_filter = make_kb_filter(kb_id) if kb_id is not None else None
        try:
            raw = col.query(
                query_embeddings=query_vec,
                n_results=n_results,
                where=where_filter,
                include=["metadatas", "documents", "distances"],
            )
        except Exception as e:
            logger.exception(f"[search] ChromaDB query failed: {e}")
            return []

        results = []
        if raw and raw["ids"] and raw["ids"][0]:
            for i, cid in enumerate(raw["ids"][0]):
                meta = raw["metadatas"][0][i] if raw["metadatas"] else {}
                doc_text = raw["documents"][0][i] if raw["documents"] else ""
                distance = raw["distances"][0][i] if raw.get("distances") else 1.0
                # cosine distance → similarity score (0~1)
                score = max(0.0, 1.0 - float(distance))
                results.append({
                    "chunk_id": cid,
                    "document_id": meta.get("doc_id", 0),
                    "filename": meta.get("filename", ""),
                    "kb_name": meta.get("kb_name", ""),
                    "kb_id": meta.get("kb_id", 0),
                    "snippet": doc_text[:300] + ("..." if len(doc_text) > 300 else ""),
                    "score": round(score, 4),
                    "distance": round(float(distance), 6),
                })

        # Filter by threshold, then sort by score desc
        results = [r for r in results if r["score"] >= min_score]
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:n_results]

    # --- Internal: ChromaDB indexing ---

    def _index_chunks(self, doc: KnowledgeDocument, chunks: list[str]) -> None:
        """Embed and insert chunks into ChromaDB."""
        if not chunks:
            return

        kb_name = doc.knowledge_base.name if doc.knowledge_base else "Unknown"
        col = _get_collection()
        model = _get_embedding_fn()

        ids = []
        metadatas = []
        for i, text in enumerate(chunks):
            ids.append(make_chunk_id(doc.kb_id, doc.id, i))
            metadatas.append({
                "doc_id": doc.id,
                "kb_id": doc.kb_id,
                "filename": doc.filename,
                "kb_name": kb_name,
                "chunk_index": i,
            })

        embeddings = model(chunks).tolist()
        col.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=chunks)

    def _delete_chunks_by_doc(self, doc_id: int) -> None:
        """Delete all chunks belonging to a document."""
        col = _get_collection()
        try:
            col.delete(where=make_doc_filter(doc_id))
        except Exception:
            pass

    def _delete_chunks_by_kb(self, kb_id: int) -> None:
        """Delete all chunks belonging to a knowledge base."""
        col = _get_collection()
        try:
            col.delete(where=make_kb_filter(kb_id))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk_previews(chunks: list[str]) -> list[dict]:
    return [
        {"index": i, "text": c[:200] + ("..." if len(c) > 200 else ""), "char_count": len(c)}
        for i, c in enumerate(chunks[:5])
    ]


def get_knowledge_service(db: Session) -> KnowledgeService:
    return KnowledgeService(db)
