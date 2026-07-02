"""Policy storage backends — JSON file vs Database."""

from __future__ import annotations
from abc import ABC, abstractmethod
import json
import os


class PolicyStorageBackend(ABC):
    """Abstract backend for reading/writing policy data."""

    @abstractmethod
    def get_policy(self, enterprise: str = "default") -> dict:
        """Return the full policy document for an enterprise."""

    @abstractmethod
    def save_policy(self, enterprise: str, policy_data: dict) -> None:
        """Write a policy document."""

    @abstractmethod
    def get_expense_type(self, enterprise: str, expense_code: str) -> dict | None:
        """Look up a single expense type by code."""

    @abstractmethod
    def list_enterprises(self) -> list[str]:
        """List available enterprises."""


class JsonFileBackend(PolicyStorageBackend):
    """Read/write policy JSON files on disk (current behavior)."""

    def __init__(self, policies_dir: str):
        self.policies_dir = policies_dir
        os.makedirs(policies_dir, exist_ok=True)

    def _file_path(self, enterprise: str) -> str:
        safe_name = enterprise.replace("/", "_").replace("\\", "_")
        return os.path.join(self.policies_dir, f"{safe_name}.json")

    def get_policy(self, enterprise: str = "default") -> dict:
        path = self._file_path(enterprise)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_policy(self, enterprise: str, policy_data: dict) -> None:
        path = self._file_path(enterprise)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(policy_data, f, ensure_ascii=False, indent=2)

    def get_expense_type(self, enterprise: str, expense_code: str) -> dict | None:
        policy = self.get_policy(enterprise)
        for et in policy.get("expense_types", []):
            if et.get("code") == expense_code:
                return et
        return None

    def list_enterprises(self) -> list[str]:
        enterprises = []
        try:
            for fname in os.listdir(self.policies_dir):
                if fname.endswith(".json"):
                    enterprises.append(fname[:-5])
        except FileNotFoundError:
            pass
        if not enterprises:
            enterprises = ["default"]
        return enterprises


class DatabaseBackend(PolicyStorageBackend):
    """Read policy data from the database (PolicyVersion.policy_json)."""

    def __init__(self, session_factory):
        """session_factory is a callable that returns a SQLAlchemy Session (e.g. SessionLocal)."""
        self._session_factory = session_factory

    def _get_published_policy(self, enterprise: str = "default") -> dict | None:
        from app.infrastructure.orm import Policy, PolicyVersion
        from app.domain.enums import PolicyStatus
        session = self._session_factory()
        try:
            policy = session.query(Policy).filter(
                Policy.enterprise == enterprise,
                Policy.status == PolicyStatus.PUBLISHED,
            ).first()
            if not policy or not policy.current_version_id:
                return None
            version = session.query(PolicyVersion).filter(
                PolicyVersion.id == policy.current_version_id
            ).first()
            if not version:
                return None
            return version.policy_json or {}
        finally:
            session.close()

    def get_policy(self, enterprise: str = "default") -> dict:
        data = self._get_published_policy(enterprise)
        return data if data is not None else {}

    def save_policy(self, enterprise: str, policy_data: dict) -> None:
        # Write-through: update policy_json on current published version
        from app.infrastructure.orm import Policy, PolicyVersion
        from app.domain.enums import PolicyStatus
        session = self._session_factory()
        try:
            policy = session.query(Policy).filter(
                Policy.enterprise == enterprise,
                Policy.status == PolicyStatus.PUBLISHED,
            ).first()
            if policy and policy.current_version_id:
                version = session.query(PolicyVersion).filter(
                    PolicyVersion.id == policy.current_version_id
                ).first()
                if version:
                    version.policy_json = policy_data
                    session.commit()
        finally:
            session.close()

    def get_expense_type(self, enterprise: str, expense_code: str) -> dict | None:
        policy = self.get_policy(enterprise)
        for et in policy.get("expense_types", []):
            if et.get("code") == expense_code:
                return et
        return None

    def list_enterprises(self) -> list[str]:
        from app.infrastructure.orm import Policy
        from app.domain.enums import PolicyStatus
        session = self._session_factory()
        try:
            rows = session.query(Policy.enterprise).filter(
                Policy.status == PolicyStatus.PUBLISHED
            ).distinct().all()
            enterprises = [r[0] for r in rows]
            if not enterprises:
                enterprises = ["default"]
            return enterprises
        finally:
            session.close()
