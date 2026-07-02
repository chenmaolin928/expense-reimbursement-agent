"""Extraction schemas — structured output with partial field support and confidence markers.

Every document upload goes through the StructuredExtractor which produces
a StructuredExtractionResult.  Downstream consumers MUST honour per-field
confidence and source markers rather than assuming all fields are present.
"""

from __future__ import annotations

from typing import Any
from enum import Enum

from pydantic import BaseModel, Field


class ExtractionSource(str, Enum):
    """Where a field value was derived from."""
    TEXT = "text"
    OCR = "ocr"
    AI_INFERENCE = "ai_inference"
    MISSING = "missing"


class FieldExtraction(BaseModel):
    """A single extracted field — value MAY be None (partial extraction)."""
    value: Any = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source: ExtractionSource = ExtractionSource.MISSING


class StructuredExtractionResult(BaseModel):
    """Complete extraction result for one document.

    ``fields`` is a dict keyed by field name (e.g. "max_amount").
    Consumers should check ``confidence`` and ``source`` on each field
    rather than assuming all fields are populated.
    """
    fields: dict[str, FieldExtraction] = Field(default_factory=dict)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    requires_review: bool = True
    raw_text_snippet: str = ""
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pre-defined schemas for LLM function-call extraction
# ---------------------------------------------------------------------------

EXPENSE_POLICY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "max_amount": {
            "type": "number",
            "description": "单次最大可报销金额（元）",
        },
        "reimbursement_ratio": {
            "type": "number",
            "description": "报销比例（0-1）",
            "minimum": 0,
            "maximum": 1,
        },
        "requires_receipt": {
            "type": "boolean",
            "description": "是否需要发票",
        },
        "requires_approval": {
            "type": "boolean",
            "description": "是否需要审批",
        },
        "approval_threshold": {
            "type": "number",
            "description": "超过此金额需审批（元）",
        },
        "max_count_per_month": {
            "type": "integer",
            "description": "每月最大报销次数",
        },
        "eligible_categories": {
            "type": "array",
            "items": {"type": "string"},
            "description": "适用费用类别列表",
        },
    },
    "required": ["max_amount", "reimbursement_ratio"],
}
