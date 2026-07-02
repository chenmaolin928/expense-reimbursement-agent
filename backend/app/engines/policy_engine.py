"""Policy Engine — unified policy query entry point.

All business code MUST go through PolicyEngine to get policy rules.
Never read policy JSON files directly outside this module.
"""

from __future__ import annotations

from app.services.policy_repository import PolicyRepository


class PolicyEngine:
    """Unified policy query engine.

    Injected with a PolicyRepository — owns no file I/O itself.
    """

    def __init__(self, repo: PolicyRepository):
        self._repo = repo

    # ---- High-level queries ----

    def get_policy(self, enterprise: str = "default") -> dict:
        """Return the full policy document for an enterprise."""
        return self._repo.get_policy(enterprise)

    def get_expense_type(self, expense_code: str, enterprise: str = "default") -> dict:
        """Look up a single expense type by code.

        Returns empty dict if the type is not found or disabled.
        """
        et = self._repo.get_expense_type(enterprise, expense_code)
        if et is None:
            return {}
        if not et.get("enabled", True):
            return {}
        return et

    def is_expense_type_supported(self, expense_code: str, enterprise: str = "default") -> bool:
        """Check whether an expense type exists and is enabled."""
        return bool(self.get_expense_type(expense_code, enterprise))

    def get_all_expense_types(self, enterprise: str = "default") -> list[dict]:
        """Return all enabled expense types.

        Disabled types (enabled=false) are excluded.
        """
        policy = self.get_policy(enterprise)
        return [et for et in policy.get("expense_types", []) if et.get("enabled", True)]
