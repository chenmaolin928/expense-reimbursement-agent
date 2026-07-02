"""Policy Service — lifecycle coordinator for Policy + PolicyVersion."""

from __future__ import annotations

from datetime import datetime
from app.domain.enums import PolicyStatus, SUB_STATUS_PARSING, SUB_STATUS_REVIEWING


class PolicyService:
    """Orchestrates the full policy lifecycle."""

    def __init__(self, session_factory=None):
        from app.database import SessionLocal
        self._session_factory = session_factory or SessionLocal

    # ---- Creation ----

    def create_from_pdf(
        self, pdf_bytes: bytes, filename: str, created_by: int,
        enterprise: str = "default", name: str = "", auto_publish: bool = False,
    ) -> dict:
        """Full upload flow: create Policy + Version, extract PDF text, build KB, AI parse.

        Args:
            pdf_bytes: Raw file bytes.
            filename: Original filename (used to detect type).
            created_by: User ID of the creator.
            enterprise: Enterprise scope.
            name: Optional policy name.
            auto_publish: If True, automatically normalize → publish after AI parse.

        Returns a dict matching PolicyUploadResponse shape.
        """
        from app.infrastructure.orm import Policy, PolicyVersion
        from app.services.knowledge_builder import KnowledgeBuilder
        from app.services.policy_parser_service import PolicyParserService

        # --- Extract text using shared text_extractor ---
        from app.services.text_extractor import extract_text
        try:
            pdf_text, _meta = extract_text(filename, pdf_bytes)
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from {filename}: {e}") from e

        if not pdf_text or not pdf_text.strip():
            raise ValueError(f"No text content could be extracted from {filename}")

        db = self._session_factory()
        try:
            # ... 2. Create Policy ...

            # 2. Create Policy
            policy = Policy(
                name=name or filename.rsplit(".", 1)[0],
                description=f"Policy from {filename}",
                policy_type="expense",
                status=PolicyStatus.DRAFT,
                enterprise=enterprise,
                created_by=created_by,
            )
            db.add(policy)
            db.flush()

            # 3. Create first PolicyVersion
            version = PolicyVersion(
                policy_id=policy.id,
                version_number=1,
                pdf_filename=filename,
                pdf_path="",
                pdf_content=pdf_text,
                status=PolicyStatus.DRAFT,
                sub_status=SUB_STATUS_PARSING,
                created_by=created_by,
            )
            db.add(version)
            db.commit()
            db.refresh(version)

            # 4. Build KB
            kb = KnowledgeBuilder(self._session_factory)
            kb_id = kb.build_for_version(version.id, pdf_text, created_by, policy_name=policy.name)

            # 5. AI Parse
            parser = PolicyParserService()
            draft = parser.parse_for_draft(pdf_text)

            # 6. Save draft
            db.refresh(version)
            version.ai_draft = draft
            version.status = PolicyStatus.DRAFT
            version.sub_status = SUB_STATUS_REVIEWING
            policy.status = PolicyStatus.DRAFT
            db.commit()

            # 7. Auto-publish if requested: normalize → publish
            if auto_publish:
                try:
                    # normalize
                    from app.services.rule_normalizer import RuleNormalizer
                    normalizer = RuleNormalizer()
                    norm_result = normalizer.normalize(draft)
                    db.refresh(version)
                    version.policy_json = norm_result.policy_json

                    # publish
                    from app.services.policy_publisher import PolicyPublisher
                    publisher = PolicyPublisher(self._session_factory)
                    pub_result = publisher.publish(version.id)
                    if pub_result.get("success"):
                        db.refresh(version)
                        db.refresh(policy)
                except Exception:
                    pass  # Auto-publish failure is non-fatal — user can do it manually

            return {
                "policy_id": policy.id,
                "version_id": version.id,
                "version_number": version.version_number,
                "status": version.status.value,
                "pdf_filename": filename,
                "kb_id": kb_id,
                "message": f"Policy '{policy.name}' v1 created from {filename}",
            }
        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Failed to create policy from PDF: {e}") from e
        finally:
            db.close()

    # ---- Lifecycle ----

    def trigger_ai_parse(self, version_id: int) -> dict | None:
        """Re-run AI parsing on an existing version. Updates ai_draft. Returns draft or None."""
        from app.infrastructure.orm import PolicyVersion
        from app.services.policy_parser_service import PolicyParserService

        db = self._session_factory()
        try:
            version = db.query(PolicyVersion).filter(PolicyVersion.id == version_id).first()
            if not version or not version.pdf_content:
                return None

            parser = PolicyParserService()
            draft = parser.parse_for_draft(version.pdf_content)
            version.ai_draft = draft
            version.status = PolicyStatus.DRAFT
            version.sub_status = SUB_STATUS_REVIEWING
            db.commit()
            return draft
        finally:
            db.close()

    def update_draft(self, version_id: int, edited_draft: dict) -> bool:
        """Manually update ai_draft. Returns True on success."""
        from app.infrastructure.orm import PolicyVersion
        db = self._session_factory()
        try:
            version = db.query(PolicyVersion).filter(PolicyVersion.id == version_id).first()
            if not version:
                return False
            version.ai_draft = edited_draft
            db.commit()
            return True
        finally:
            db.close()

    def normalize_draft(self, version_id: int) -> dict | None:
        """Normalize ai_draft -> policy_json using RuleNormalizer. Returns NormalizationResult dict."""
        from app.infrastructure.orm import PolicyVersion
        from app.services.rule_normalizer import RuleNormalizer

        db = self._session_factory()
        try:
            version = db.query(PolicyVersion).filter(PolicyVersion.id == version_id).first()
            if not version or not version.ai_draft:
                return None

            normalizer = RuleNormalizer()
            result = normalizer.normalize(version.ai_draft)
            version.policy_json = result.policy_json
            db.commit()
            return {
                "policy_json": result.policy_json,
                "warnings": result.warnings,
            }
        finally:
            db.close()

    def publish(self, version_id: int) -> dict:
        """Publish a version. Returns publisher result dict."""
        from app.services.policy_publisher import PolicyPublisher
        publisher = PolicyPublisher(self._session_factory)
        return publisher.publish(version_id)

    def archive(self, version_id: int) -> bool:
        """Archive a policy version."""
        from app.infrastructure.orm import Policy, PolicyVersion
        db = self._session_factory()
        try:
            version = db.query(PolicyVersion).filter(PolicyVersion.id == version_id).first()
            if not version:
                return False
            version.status = PolicyStatus.ARCHIVED
            version.archived_at = datetime.utcnow()
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

    # ---- Queries ----

    def list_policies(self) -> list[dict]:
        """List all policies."""
        from app.infrastructure.orm import Policy
        db = self._session_factory()
        try:
            policies = db.query(Policy).order_by(Policy.updated_at.desc()).all()
            return [
                {
                    "id": p.id, "name": p.name, "description": p.description or "",
                    "policy_type": p.policy_type, "status": p.status.value,
                    "current_version_number": None,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in policies
            ]
        finally:
            db.close()

    def get_policy(self, policy_id: int) -> dict | None:
        """Get policy detail."""
        from app.infrastructure.orm import Policy
        db = self._session_factory()
        try:
            p = db.query(Policy).filter(Policy.id == policy_id).first()
            if not p:
                return None
            return {
                "id": p.id, "name": p.name, "description": p.description or "",
                "policy_type": p.policy_type, "status": p.status.value,
                "enterprise": p.enterprise, "current_version_id": p.current_version_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
        finally:
            db.close()

    def get_versions(self, policy_id: int) -> list[dict]:
        """List versions for a policy."""
        from app.infrastructure.orm import PolicyVersion
        db = self._session_factory()
        try:
            versions = db.query(PolicyVersion).filter(
                PolicyVersion.policy_id == policy_id
            ).order_by(PolicyVersion.version_number.desc()).all()
            return [
                {
                    "id": v.id, "version_number": v.version_number,
                    "status": v.status.value, "pdf_filename": v.pdf_filename,
                    "kb_id": v.kb_id,
                    "published_at": v.published_at.isoformat() if v.published_at else None,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ]
        finally:
            db.close()

    def get_version_detail(self, version_id: int) -> dict | None:
        """Get full version detail including ai_draft and policy_json."""
        from app.infrastructure.orm import PolicyVersion
        db = self._session_factory()
        try:
            v = db.query(PolicyVersion).filter(PolicyVersion.id == version_id).first()
            if not v:
                return None
            return {
                "id": v.id, "version_number": v.version_number,
                "status": v.status.value, "pdf_filename": v.pdf_filename,
                "kb_id": v.kb_id,
                "ai_draft": v.ai_draft,
                "policy_json": v.policy_json,
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
        finally:
            db.close()

    def get_current_policy(self, enterprise: str = "default") -> dict | None:
        """Get the currently published policy's policy_json."""
        from app.infrastructure.orm import Policy, PolicyVersion
        db = self._session_factory()
        try:
            policy = db.query(Policy).filter(
                Policy.enterprise == enterprise,
                Policy.status == PolicyStatus.PUBLISHED,
            ).first()
            if not policy or not policy.current_version_id:
                return None
            version = db.query(PolicyVersion).filter(
                PolicyVersion.id == policy.current_version_id
            ).first()
            return version.policy_json if version else None
        finally:
            db.close()
