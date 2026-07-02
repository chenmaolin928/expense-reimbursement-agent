"""Rule Normalizer — transforms AI draft into executable Policy JSON.

Supports both new format (policy_doc.domains[].rules[]) and legacy format
(flat expense_types[]), auto-detecting by presence of the 'policy_doc' key.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class NormalizationResult:
    """Result of normalizing an AI draft."""
    policy_json: dict
    warnings: list[str] = field(default_factory=list)
    excluded_count: int = 0
    is_valid: bool = True


class RuleNormalizer:
    """Normalize AI draft to clean, executable policy JSON.

    Always outputs the domains[].rules[] structure — never the legacy flat format.
    """

    def normalize(self, ai_draft: dict) -> NormalizationResult:
        """Transform an AI draft into a clean policy JSON dict.

        Input ai_draft shape (new format):
        {
            "policy_doc": {
                "doc_id": "...", "title": "...", "version": "...",
                "domains": [
                    {
                        "id": "D001", "name": "餐饮",
                        "rules": [
                            {"id": "R001", "type": "ratio", "value": 0.6,
                             "raw_text": "...", "confidence": 0.95,
                             "ai_reasoning": "..."},
                        ]
                    }
                ]
            },
            "warnings": [...],
            "metadata": {...}
        }

        Input ai_draft shape (legacy flat format — backward compat):
        {
            "enterprise": "default",
            "description": "...",
            "expense_types": [{code, name, reimbursement_ratio, ...}],
            "warnings": [...],
            "metadata": {...}
        }

        Output policy_json shape:
        {
            "doc_id": "", "title": "", "version": "",
            "domains": [{id, name, rules: [{id, type, title, scope,
                                           condition, value, unit, raw_text}]}]
        }
        """

        warnings = list(ai_draft.get("warnings", []))

        if "policy_doc" in ai_draft:
            # New format — strip AI metadata from rules
            return self._normalize_v2(ai_draft["policy_doc"], warnings)

        # Legacy flat format — convert via domain synthesis
        return self._normalize_v1(ai_draft, warnings)

    def _normalize_v2(self, policy_doc: dict, warnings: list[str]) -> NormalizationResult:
        """Normalize new format: keep domains[].rules[], strip AI metadata."""
        clean_domains = []
        for domain in policy_doc.get("domains", []):
            clean_rules = []
            for rule in domain.get("rules", []):
                clean_rules.append({
                    "id": rule.get("id", ""),
                    "type": rule.get("type", "other"),
                    "title": rule.get("title", ""),
                    "scope": {
                        "role": rule.get("scope", {}).get("role"),
                        "region": rule.get("scope", {}).get("region"),
                        "amount_range": rule.get("scope", {}).get("amount_range"),
                    },
                    "condition": rule.get("condition", ""),
                    "value": rule.get("value"),
                    "unit": rule.get("unit", ""),
                    "raw_text": rule.get("raw_text", ""),
                })
            clean_domains.append({
                "id": domain.get("id", ""),
                "name": domain.get("name", ""),
                "rules": clean_rules,
            })

        policy_json = {
            "doc_id": policy_doc.get("doc_id", ""),
            "title": policy_doc.get("title", ""),
            "version": policy_doc.get("version", ""),
            "domains": clean_domains,
        }

        return NormalizationResult(
            policy_json=policy_json,
            warnings=warnings,
            excluded_count=0,
            is_valid=len(clean_domains) > 0,
        )

    def _normalize_v1(self, ai_draft: dict, warnings: list[str]) -> NormalizationResult:
        """Normalize legacy flat expense_types format into new domains[].rules[].

        This reverse-engineers a domain+rule structure from the flat list.
        """
        raw_types = ai_draft.get("expense_types", [])
        domains = []

        for et in raw_types:
            code = et.get("code", "")
            name = et.get("name", code)
            rules = []

            # Create a ratio rule
            ratio = float(et.get("reimbursement_ratio", 0.8))
            rules.append({
                "id": f"{code}_ratio",
                "type": "ratio",
                "title": f"{name}报销比例",
                "scope": {"role": None, "region": None, "amount_range": None},
                "condition": "",
                "value": ratio,
                "unit": "percent",
                "raw_text": f"{name}报销比例为{ratio * 100:.0f}%",
            })

            # Create a limit rule
            cap = et.get("cap")
            if cap is not None:
                rules.append({
                    "id": f"{code}_cap",
                    "type": "limit",
                    "title": f"{name}单次上限",
                    "scope": {"role": None, "region": None, "amount_range": None},
                    "condition": "",
                    "value": float(cap),
                    "unit": "yuan",
                    "raw_text": f"{name}单次报销不超过{cap}元",
                })

            # Create an approval rule
            approval_over = float(et.get("approval_over", 0))
            if approval_over > 0:
                rules.append({
                    "id": f"{code}_approval",
                    "type": "approval",
                    "title": f"{name}审批阈值",
                    "scope": {"role": None, "region": None, "amount_range": None},
                    "condition": f"超过{approval_over:.0f}元",
                    "value": approval_over,
                    "unit": "yuan",
                    "raw_text": f"{name}超过{approval_over:.0f}元需审批",
                })

            # Create a requirement rule for guest list
            if et.get("need_guest", False):
                rules.append({
                    "id": f"{code}_guest",
                    "type": "requirement",
                    "title": f"{name}需宾客名单",
                    "scope": {"role": None, "region": None, "amount_range": None},
                    "condition": "",
                    "value": None,
                    "unit": "",
                    "raw_text": f"{name}需要提供宾客名单",
                })

            domains.append({
                "id": code,
                "name": name,
                "rules": rules,
            })

        policy_json = {
            "doc_id": "",
            "title": ai_draft.get("description", ""),
            "version": "",
            "domains": domains,
        }

        return NormalizationResult(
            policy_json=policy_json,
            warnings=warnings,
            excluded_count=0,
            is_valid=len(domains) > 0,
        )
