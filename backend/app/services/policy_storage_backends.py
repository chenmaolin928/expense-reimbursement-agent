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
        """Look up a single expense type by code (legacy)."""

    def get_domain(self, enterprise: str, domain_name: str) -> dict | None:
        """Look up a single domain by name (new format)."""
        policy = self.get_policy(enterprise)
        for domain in policy.get("domains", []):
            if domain.get("name") == domain_name:
                return domain
        return None

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
        # Try legacy flat format first
        for et in policy.get("expense_types", []):
            if et.get("code") == expense_code:
                return et
        # New format: fallback to domain matching
        for domain in policy.get("domains", []):
            d_name = domain.get("name", "")
            mapping = {
                "meals": ["餐饮", "餐饮费", "餐费"],
                "travel": ["差旅", "差旅费", "出差"],
                "transportation": ["交通", "交通费", "通勤"],
                "office_supplies": ["办公用品", "办公"],
                "entertainment": ["商务招待", "招待", "招待费"],
            }
            keywords = mapping.get(expense_code, [])
            if any(kw in d_name for kw in keywords):
                return self._domain_to_expense_type(domain, expense_code)
        return None

    def get_domain(self, enterprise: str, domain_name: str) -> dict | None:
        policy = self.get_policy(enterprise)
        for domain in policy.get("domains", []):
            if domain.get("name") == domain_name:
                return domain
        return None

    @staticmethod
    def _domain_to_expense_type(domain: dict, code: str) -> dict:
        """Convert a domain+d rules to flat expense_type dict."""
        name = domain.get("name", code)
        rules = domain.get("rules", [])
        ratio = 0.8
        cap = None
        approval_over = 0.0
        need_guest = False
        need_invoice = True
        need_attachment = False
        for rule in rules:
            rtype = rule.get("type", "")
            value = rule.get("value")
            raw = rule.get("raw_text", "")
            if rtype == "ratio" and value is not None:
                ratio = float(value)
            elif rtype == "limit" and value is not None:
                cap = float(value)
            elif rtype == "approval" and value is not None:
                approval_over = float(value)
            elif rtype == "requirement":
                if "发票" in raw or "invoice" in raw.lower():
                    need_invoice = True
                if "附件" in raw or "attachment" in raw.lower():
                    need_attachment = True
                if "宾客" in raw or "guest" in raw.lower() or "客户" in raw:
                    need_guest = True
        return {
            "code": code, "name": name,
            "reimbursement_ratio": ratio,
            "limit_per_person": None, "cap": cap,
            "approval_over": approval_over,
            "need_guest": need_guest,
            "need_invoice": need_invoice,
            "need_attachment": need_attachment,
            "enabled": True,
        }

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
        # Legacy format
        for et in policy.get("expense_types", []):
            if et.get("code") == expense_code:
                return et
        # New format via domain
        for domain in policy.get("domains", []):
            d_name = domain.get("name", "")
            mapping = {
                "meals": ["餐饮", "餐饮费", "餐费"],
                "travel": ["差旅", "差旅费", "出差"],
                "transportation": ["交通", "交通费", "通勤"],
                "office_supplies": ["办公用品", "办公"],
                "entertainment": ["商务招待", "招待", "招待费"],
            }
            keywords = mapping.get(expense_code, [])
            if any(kw in d_name for kw in keywords):
                return JsonFileBackend._domain_to_expense_type(domain, expense_code)
        return None

    def get_domain(self, enterprise: str, domain_name: str) -> dict | None:
        policy = self.get_policy(enterprise)
        for domain in policy.get("domains", []):
            if domain.get("name") == domain_name:
                return domain
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
