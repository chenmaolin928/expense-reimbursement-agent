"""Policy Engine — unified policy query entry point.

All business code MUST go through PolicyEngine to get policy rules.
Never read policy JSON files directly outside this module.

Supports two policy JSON formats:
  - New: {"domains": [{"id", "name", "rules": [{id, type, value, ...}]}]}
  - Legacy: {"expense_types": [{code, name, reimbursement_ratio, ...}]}

The get_expense_type() method auto-detects format and bridges to
the new rule-based system by resolving rules into expense_type-like dicts.
"""

from __future__ import annotations

from app.services.policy_repository import PolicyRepository


class PolicyEngine:
    """Unified policy query engine.

    Injected with a PolicyRepository — owns no file I/O itself.
    """

    def __init__(self, repo: PolicyRepository):
        self._repo = repo

    # ---- New domain API ----

    def get_domain(self, domain_name: str, enterprise: str = "default") -> dict:
        """Look up a single domain by name, returning its rules.

        Returns empty dict if the domain is not found.
        """
        return self._repo.get_domain(enterprise, domain_name) or {}

    def get_all_domains(self, enterprise: str = "default") -> list[dict]:
        """Return all domains from the policy."""
        policy = self.get_policy(enterprise)
        return policy.get("domains", [])

    # ---- Legacy backward-compat API (bridged via rules) ----

    def get_expense_type(self, expense_code: str, enterprise: str = "default") -> dict:
        """Look up a single expense type by code (legacy compat).

        Internally resolves domains[].rules[] to the old flat format.
        Falls back to legacy expense_types[] if the policy is old format.
        """
        policy = self.get_policy(enterprise)

        # Try legacy format first
        if "expense_types" in policy:
            for et in policy["expense_types"]:
                if et.get("code") == expense_code and et.get("enabled", True):
                    return et
            return {}

        # New format: find the domain matching the code, resolve rules
        for domain in policy.get("domains", []):
            d_name = domain.get("name", "")
            if self._domain_matches_code(d_name, expense_code):
                return self._resolve_rules_to_expense_type(domain, expense_code)

        return {}

    def is_expense_type_supported(self, expense_code: str, enterprise: str = "default") -> bool:
        """Check whether an expense type exists and is enabled."""
        return bool(self.get_expense_type(expense_code, enterprise))

    def get_all_expense_types(self, enterprise: str = "default") -> list[dict]:
        """Return all enabled expense types (legacy compat).

        Disabled types (enabled=false) are excluded.
        Supports both new and old policy formats.
        """
        policy = self.get_policy(enterprise)

        # Legacy format
        if "expense_types" in policy:
            return [et for et in policy["expense_types"] if et.get("enabled", True)]

        # New format: resolve each domain to an expense_type
        result = []
        for domain in policy.get("domains", []):
            d_name = domain.get("name", "")
            code = self._domain_name_to_fallback_code(d_name, domain.get("id", ""))
            et = self._resolve_rules_to_expense_type(domain, code)
            if et.get("enabled", True):
                result.append(et)
        return result

    # ---- Raw policy ----

    def get_policy(self, enterprise: str = "default") -> dict:
        """Return the full policy document for an enterprise."""
        return self._repo.get_policy(enterprise)

    # ---- Internal helpers ----

    @staticmethod
    def _resolve_rules_to_expense_type(domain: dict, code: str) -> dict:
        """Resolve a domain's rules into the legacy flat expense_type dict format."""
        name = domain.get("name", code)
        rules = domain.get("rules", [])

        ratio = 0.8
        cap = None
        approval_over = 0.0
        need_guest = False
        need_invoice = True
        need_attachment = False
        enabled = True

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
            "code": code,
            "name": name,
            "reimbursement_ratio": ratio,
            "limit_per_person": None,
            "cap": cap,
            "approval_over": approval_over,
            "need_guest": need_guest,
            "need_invoice": need_invoice,
            "need_attachment": need_attachment,
            "enabled": enabled,
        }

    @staticmethod
    def _domain_matches_code(domain_name: str, expense_code: str) -> bool:
        """Check if a domain name corresponds to an expense code."""
        mapping = {
            "meals": ["餐饮", "餐饮费", "餐费", "伙食", "食堂"],
            "travel": ["差旅", "差旅费", "出差", "旅行", "交通住宿"],
            "transportation": ["交通", "交通费", "通勤", "出行"],
            "office_supplies": ["办公用品", "办公", "文具", "耗材"],
            "entertainment": ["商务招待", "招待", "招待费", "接待"],
        }
        keywords = mapping.get(expense_code, [])
        return any(kw in domain_name for kw in keywords)

    @staticmethod
    def _domain_name_to_fallback_code(domain_name: str, domain_id: str) -> str:
        """Map a domain name to a code for backward compat (last resort)."""
        mapping = {
            "餐饮": "meals", "餐饮费": "meals", "餐费": "meals",
            "差旅": "travel", "差旅费": "travel", "出差": "travel",
            "交通": "transportation", "交通费": "transportation", "通勤": "transportation",
            "办公用品": "office_supplies", "办公": "office_supplies",
            "商务招待": "entertainment", "招待": "entertainment", "招待费": "entertainment",
        }
        for key, code in mapping.items():
            if key in domain_name:
                return code
        return domain_id.lower().replace(" ", "_") if domain_id else "other"
