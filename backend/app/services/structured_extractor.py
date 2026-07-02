"""Structured extractor — single entry point for LLM-guided document extraction.

Every document upload flows through ``StructuredExtractor.extract()``.
The extractor:
  1. Calls the LLM with a JSON schema (function-call mode).
  2. Validates the response against the schema.
  3. Retries once if validation fails.
  4. If still invalid, returns a result with ``requires_review=True``.

No document bypasses this pipeline — raw text is never used directly.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.schemas.extraction import (
    EXPENSE_POLICY_SCHEMA,
    FieldExtraction,
    ExtractionSource,
    StructuredExtractionResult,
)

logger = logging.getLogger(__name__)


class StructuredExtractor:
    """Unified structured extraction entry point.

    Every document upload must pass through ``extract()``.
    The method signature accepts any Pydantic-style JSON schema; defaults to
    ``EXPENSE_POLICY_SCHEMA`` when none is provided.

    Usage::

        extractor = StructuredExtractor(llm_client)
        result = extractor.extract(policy_text)
        if result.requires_review:
            notify_admin(f"Extraction needs review: {result.warnings}")
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm_client = llm_client

    def extract(
        self,
        text: str,
        schema: dict | None = None,
        max_retries: int = 1,
    ) -> StructuredExtractionResult:
        """Extract structured data from *text* using *schema*.

        Args:
            text: Raw document text (already quality-assessed and routed).
            schema: JSON Schema dict for the target extraction shape.
            max_retries: Number of re-tries after a validation failure.

        Returns:
            A ``StructuredExtractionResult``.  Check ``requires_review``
            before consuming downstream.
        """
        if not text or not text.strip():
            return StructuredExtractionResult(
                overall_confidence=0.0,
                requires_review=True,
                raw_text_snippet="",
                warnings=["Input text is empty — nothing to extract."],
            )

        effective_schema = schema or EXPENSE_POLICY_SCHEMA
        attempt: StructuredExtractionResult | None = None

        for retry in range(max_retries + 1):
            try:
                attempt = self._call_llm(text, effective_schema)
                if self._validate_against_schema(attempt, effective_schema):
                    break
            except Exception as exc:
                logger.warning("LLM extraction attempt %d failed: %s", retry, exc)
                attempt = None

        if not attempt or not self._validate_against_schema(attempt, effective_schema):
            return StructuredExtractionResult(
                fields={},
                overall_confidence=0.0,
                requires_review=True,
                raw_text_snippet=text[:500],
                warnings=["LLM extraction failed schema validation — manual review required."],
            )

        return attempt

    def _call_llm(self, text: str, schema: dict) -> StructuredExtractionResult:
        """Call the LLM with function-call extraction.

        Override this in subclasses or inject a real client via ``__init__``.
        The default implementation raises ``NotImplementedError``.
        """
        raise NotImplementedError(
            "StructuredExtractor._call_llm is abstract — inject a real LLM client."
        )

    # ------------------------------------------------------------------
    # Schema validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_against_schema(
        result: StructuredExtractionResult,
        schema: dict,
    ) -> bool:
        """Check that every *required* field in *schema* has a non-None value."""
        required: list[str] = schema.get("required") or []
        for field_name in required:
            fe = result.fields.get(field_name)
            if fe is None:
                return False
            if fe.value is None and fe.source == ExtractionSource.MISSING:
                return False
        return True

    # ------------------------------------------------------------------
    # Convenience factories (useful in tests / simple scenarios)
    # ------------------------------------------------------------------

    @staticmethod
    def empty_result(text: str = "", warnings: list[str] | None = None) -> StructuredExtractionResult:
        """Return an empty result requiring review."""
        return StructuredExtractionResult(
            fields={},
            overall_confidence=0.0,
            requires_review=True,
            raw_text_snippet=text[:500],
            warnings=warnings or [],
        )
