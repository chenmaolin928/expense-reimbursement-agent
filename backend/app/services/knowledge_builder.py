"""Knowledge Builder — builds ChromaDB knowledge bases from Policy PDFs."""

from __future__ import annotations


class KnowledgeBuilder:
    """Build and manage knowledge bases tied to PolicyVersion records."""

    def __init__(self, session_factory=None):
        """session_factory should be a callable that returns a SQLAlchemy Session."""
        from app.database import SessionLocal
        self._session_factory = session_factory or SessionLocal

    def build_for_version(
        self, version_id: int, pdf_text: str, created_by: int,
        policy_name: str = "",
    ) -> int:
        """Create a KB from PDF text, chunk it, embed it. Returns kb_id."""
        db = self._session_factory()
        try:
            from app.infrastructure.orm import PolicyVersion
            from app.services.knowledge_service import KnowledgeService

            version = db.query(PolicyVersion).filter(
                PolicyVersion.id == version_id
            ).first()
            if not version:
                raise ValueError(f"PolicyVersion {version_id} not found")

            kb_name = f"Policy v{version.version_number}"
            if policy_name:
                kb_name += f" - {policy_name}"

            ks = KnowledgeService(db)
            kb = ks.create_base(
                name=kb_name,
                description=f"Auto-generated from PDF: {version.pdf_filename or 'unknown'}",
                created_by=created_by,
            )

            ks.add_document(
                kb_id=kb.id,
                filename=version.pdf_filename or "policy.pdf",
                content=pdf_text,
            )

            version.kb_id = kb.id
            db.commit()

            return kb.id
        finally:
            db.close()

    def rebuild_for_version(self, version_id: int) -> int | None:
        """Delete existing KB and rebuild it. Returns new kb_id or None."""
        db = self._session_factory()
        try:
            from app.infrastructure.orm import PolicyVersion

            version = db.query(PolicyVersion).filter(
                PolicyVersion.id == version_id
            ).first()
            if not version:
                return None

            old_kb_id = version.kb_id
            pdf_text = version.pdf_content or ""
            created_by = version.created_by

            if old_kb_id:
                from app.infrastructure.orm import KnowledgeBase
                old_kb = db.query(KnowledgeBase).filter(
                    KnowledgeBase.id == old_kb_id
                ).first()
                if old_kb:
                    db.delete(old_kb)
                    db.commit()

            return self.build_for_version(version_id, pdf_text, created_by)
        finally:
            db.close()

    def delete_for_version(self, version_id: int) -> bool:
        """Delete the KB associated with a PolicyVersion. Returns True if deleted."""
        db = self._session_factory()
        try:
            from app.infrastructure.orm import PolicyVersion, KnowledgeBase

            version = db.query(PolicyVersion).filter(
                PolicyVersion.id == version_id
            ).first()
            if not version or not version.kb_id:
                return False

            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.id == version.kb_id
            ).first()
            if kb:
                db.delete(kb)
                version.kb_id = None
                db.commit()
                return True
            return False
        finally:
            db.close()
