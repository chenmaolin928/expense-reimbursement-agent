"""Policy Repository — facade over pluggable storage backends."""

from __future__ import annotations
from app.services.policy_storage_backends import PolicyStorageBackend, JsonFileBackend


class PolicyRepository:
    """Read/write enterprise policy data through a pluggable backend."""

    def __init__(self, policies_dir_or_backend):
        """Accept either a directory path (backward-compatible) or a PolicyStorageBackend instance."""
        if isinstance(policies_dir_or_backend, PolicyStorageBackend):
            self._backend = policies_dir_or_backend
        else:
            self._backend = JsonFileBackend(policies_dir_or_backend)

    def get_policy(self, enterprise: str = "default") -> dict:
        return self._backend.get_policy(enterprise)

    def save_policy(self, enterprise: str, policy_data: dict) -> None:
        self._backend.save_policy(enterprise, policy_data)

    def get_expense_type(self, enterprise: str, expense_code: str) -> dict | None:
        return self._backend.get_expense_type(enterprise, expense_code)

    def list_enterprises(self) -> list[str]:
        return self._backend.list_enterprises()

    # ---- New methods (not on backend — convenience) ----

    def get_version_history(self, enterprise: str = "default") -> list[dict]:
        """Return version history for an enterprise's policy (DB only)."""
        from app.services.policy_storage_backends import DatabaseBackend
        if not isinstance(self._backend, DatabaseBackend):
            return []
        from app.infrastructure.orm import Policy, PolicyVersion
        session = self._backend._session_factory()
        try:
            policy = session.query(Policy).filter(Policy.enterprise == enterprise).first()
            if not policy:
                return []
            versions = session.query(PolicyVersion).filter(
                PolicyVersion.policy_id == policy.id
            ).order_by(PolicyVersion.version_number.desc()).all()
            return [
                {
                    "id": v.id, "version_number": v.version_number,
                    "status": v.status.value, "pdf_filename": v.pdf_filename,
                    "published_at": v.published_at.isoformat() if v.published_at else None,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ]
        finally:
            session.close()

    def get_policy_draft(self, enterprise: str = "default") -> dict | None:
        """Return the latest draft version's ai_draft (DB only)."""
        from app.services.policy_storage_backends import DatabaseBackend
        if not isinstance(self._backend, DatabaseBackend):
            return None
        from app.infrastructure.orm import Policy, PolicyVersion
        from app.domain.enums import PolicyStatus
        session = self._backend._session_factory()
        try:
            policy = session.query(Policy).filter(Policy.enterprise == enterprise).first()
            if not policy:
                return None
            version = session.query(PolicyVersion).filter(
                PolicyVersion.policy_id == policy.id,
                PolicyVersion.status.in_([PolicyStatus.DRAFT, PolicyStatus.REVIEWING]),
            ).order_by(PolicyVersion.version_number.desc()).first()
            return version.ai_draft if version else None
        finally:
            session.close()

    def publish_policy(self, enterprise: str, policy_data: dict) -> None:
        """Publish policy to the backend (save + any backend-specific publish logic)."""
        self._backend.save_policy(enterprise, policy_data)
