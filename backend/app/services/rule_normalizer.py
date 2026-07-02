"""Rule Normalizer — transforms AI draft into executable Policy JSON."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class NormalizationResult:
    """Result of normalizing an AI draft."""
    policy_json: dict
    warnings: list[str] = field(default_factory=list)
    excluded_count: int = 0  # expense types removed (unknown code)
    is_valid: bool = True


# Known valid expense codes for the system
VALID_EXPENSE_CODES = {
    "meals", "travel", "transportation", "office_supplies", "entertainment",
}

# Default values for missing fields
DEFAULTS = {
    "enabled": True,
    "max_amount": None,
    "reimbursement_ratio": 1.0,
    "requires_approval": False,
    "approval_threshold": None,
    "requires_guest_list": False,
    "notes": "",
}


class RuleNormalizer:
    """Normalize AI draft to clean, executable policy JSON."""

    def normalize(self, ai_draft: dict) -> NormalizationResult:
        """Transform an AI draft into a clean policy_json dict.

        Input ai_draft shape (from AI parser):
        {
            "enterprise": "default",
            "description": "...",
            "expense_types": [
                {
                    "code": "meals",
                    "name": "餐饮费",
                    "reimbursement_ratio": 0.6,
                    "max_amount": 500,
                    "requires_approval": false,
                    ...,
                    "confidence": 0.95,
                    "source_text": "原文引用...",
                    "ai_reasoning": "AI分析..."
                }
            ],
            "warnings": ["..."],
            "metadata": {...}
        }

        Output policy_json shape (for engines):
        {
            "enterprise": "default",
            "description": "...",
            "expense_types": [
                {
                    "code": "meals",
                    "name": "餐饮费",
                    "reimbursement_ratio": 0.6,
                    "max_amount": 500,
                    "requires_approval": false,
                    ...
                }
            ]
        }
        """
        warnings = list(ai_draft.get("warnings", []))

        raw_types = ai_draft.get("expense_types", [])
        clean_types = []
        excluded = 0

        for et in raw_types:
            code = et.get("code", "")

            # Exclude unknown expense codes
            if code not in VALID_EXPENSE_CODES:
                warnings.append(f"Unknown expense code '{code}' — excluded from policy")
                excluded += 1
                continue

            # Build clean type: copy known fields, strip AI metadata
            clean = {
                "code": code,
                "name": et.get("name", code),
                "enabled": et.get("enabled", DEFAULTS["enabled"]),
                "reimbursement_ratio": et.get("reimbursement_ratio", DEFAULTS["reimbursement_ratio"]),
                "max_amount": et.get("max_amount", DEFAULTS["max_amount"]),
                "requires_approval": et.get("requires_approval", DEFAULTS["requires_approval"]),
                "approval_threshold": et.get("approval_threshold", DEFAULTS["approval_threshold"]),
                "requires_guest_list": et.get("requires_guest_list", DEFAULTS["requires_guest_list"]),
                "notes": et.get("notes", DEFAULTS["notes"]),
            }

            # Validate ratio range
            ratio = clean["reimbursement_ratio"]
            if ratio is not None and (ratio < 0 or ratio > 1):
                warnings.append(f"Invalid reimbursement_ratio {ratio} for {code} — clamped to 0-1")
                clean["reimbursement_ratio"] = max(0.0, min(1.0, ratio))

            clean_types.append(clean)

        policy_json = {
            "enterprise": ai_draft.get("enterprise", "default"),
            "description": ai_draft.get("description", ""),
            "expense_types": clean_types,
        }

        return NormalizationResult(
            policy_json=policy_json,
            warnings=warnings,
            excluded_count=excluded,
            is_valid=len(clean_types) > 0,
        )
