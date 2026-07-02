"""Policy Publisher — validates and publishes policy versions."""

from __future__ import annotations
from datetime import datetime


class PolicyPublisher:
    """Publish policy versions through the storage backend."""

    def __init__(self, session_factory=None):
        from app.database import SessionLocal
        self._session_factory = session_factory or SessionLocal

    def publish(self, version_id: int, repository=None) -> dict:
        """Publish a PolicyVersion. Validates policy_json, marks PUBLISHED, writes to backend.

        Returns: {"success": bool, "message": str, "policy_id": int, "version_id": int}
        """
        from app.infrastructure.orm import Policy, PolicyVersion
        from app.domain.enums import PolicyStatus

        db = self._session_factory()
        try:
            version = db.query(PolicyVersion).filter(PolicyVersion.id == version_id).first()
            if not version:
                return {"success": False, "message": f"Version {version_id} not found", "policy_id": 0, "version_id": version_id}

            if not version.policy_json:
                return {"success": False, "message": "Version has no policy_json — run normalize first", "policy_id": version.policy_id, "version_id": version_id}

            # Validate policy_json has expense_types or domains
            pj = version.policy_json
            if not pj.get("expense_types") and not pj.get("domains"):
                return {"success": False, "message": "policy_json has no expense_types or domains", "policy_id": version.policy_id, "version_id": version_id}

            policy = db.query(Policy).filter(Policy.id == version.policy_id).first()
            if not policy:
                return {"success": False, "message": f"Policy {version.policy_id} not found", "policy_id": version.policy_id, "version_id": version_id}

            # Archive previously published version if exists
            if policy.current_version_id:
                old_version = db.query(PolicyVersion).filter(
                    PolicyVersion.id == policy.current_version_id
                ).first()
                if old_version and old_version.id != version_id:
                    old_version.status = PolicyStatus.ARCHIVED
                    old_version.archived_at = datetime.utcnow()

            # Publish this version
            version.status = PolicyStatus.PUBLISHED
            version.published_at = datetime.utcnow()
            policy.status = PolicyStatus.PUBLISHED
            policy.current_version_id = version.id

            # Write to storage backend
            if repository:
                repository.save_policy(policy.enterprise, version.policy_json)
            else:
                # Fallback: use default JSON repository if none provided
                try:
                    from app.services.policy_repository import PolicyRepository
                    from app.config import settings
                    repo = PolicyRepository(settings.policy.policies_dir)
                    repo.save_policy(policy.enterprise, version.policy_json)
                except Exception:
                    pass  # Non-fatal — DB state is still correct

            db.commit()

            return {
                "success": True,
                "message": f"Policy v{version.version_number} published",
                "policy_id": policy.id,
                "version_id": version.id,
            }
        except Exception as e:
            db.rollback()
            return {"success": False, "message": str(e), "policy_id": 0, "version_id": version_id}
        finally:
            db.close()

    def rollback_publish(self, version_id: int) -> bool:
        """DEPRECATED: Use PolicyLifecycleService.activate_version() instead.

        Kept for backward compatibility — maps to activate_version logic.
        """
        from app.services.policy_lifecycle import PolicyLifecycleService
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            lifecycle = PolicyLifecycleService(db)
            result = lifecycle.activate_version(
                policy_id=0,  # resolved inside
                version_id=version_id,
                actor_id=0,
            )
            return result.success
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()
        finally:
            db.close()
