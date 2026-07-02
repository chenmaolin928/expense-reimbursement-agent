"""Tests for extraction schemas and StructuredExtractor."""
import pytest
from app.schemas.extraction import (
    StructuredExtractionResult,
    FieldExtraction,
    ExtractionSource,
    EXPENSE_POLICY_SCHEMA,
)
from app.services.structured_extractor import StructuredExtractor


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestStructuredExtractionResult:
    def test_empty_result_defaults(self):
        r = StructuredExtractionResult()
        assert r.requires_review is True
        assert r.overall_confidence == 0.0
        assert r.fields == {}
        assert r.warnings == []

    def test_partial_fields_allowed(self):
        r = StructuredExtractionResult(
            fields={
                "max_amount": FieldExtraction(
                    value=500.0,
                    confidence=0.9,
                    source=ExtractionSource.TEXT,
                ),
                "reimbursement_ratio": FieldExtraction(
                    value=None,
                    confidence=0.0,
                    source=ExtractionSource.MISSING,
                ),
            },
            overall_confidence=0.45,
            requires_review=True,
            raw_text_snippet="出差报销标准：...",
            warnings=["reimbursement_ratio 未提取到"],
        )
        assert r.fields["max_amount"].value == 500.0
        assert r.fields["reimbursement_ratio"].value is None
        assert r.overall_confidence == 0.45
        assert r.requires_review is True
        assert len(r.warnings) == 1

    def test_serialize_deserialize(self):
        """Ensure Pydantic round-trip works."""
        r = StructuredExtractionResult(
            fields={
                "max_amount": FieldExtraction(value=300.0, confidence=0.8, source=ExtractionSource.TEXT),
            },
            overall_confidence=0.8,
            requires_review=False,
            raw_text_snippet="test",
        )
        dumped = r.model_dump()
        loaded = StructuredExtractionResult.model_validate(dumped)
        assert loaded.fields["max_amount"].value == 300.0
        assert loaded.overall_confidence == 0.8


class TestEXPENSE_POLICY_SCHEMA:
    def test_has_required_fields(self):
        assert "max_amount" in EXPENSE_POLICY_SCHEMA["required"]
        assert "reimbursement_ratio" in EXPENSE_POLICY_SCHEMA["required"]

    def test_has_properties(self):
        assert len(EXPENSE_POLICY_SCHEMA["properties"]) >= 5


# ---------------------------------------------------------------------------
# StructuredExtractor tests
# ---------------------------------------------------------------------------

class FakeExtractor(StructuredExtractor):
    """Subclass that returns deterministic results for testing."""
    def __init__(self, should_succeed: bool = True):
        super().__init__()
        self._should_succeed = should_succeed

    def _call_llm(self, text: str, schema: dict) -> StructuredExtractionResult:
        if not self._should_succeed:
            return StructuredExtractionResult(
                fields={},
                overall_confidence=0.0,
                requires_review=True,
                raw_text_snippet=text[:500],
                warnings=["Simulated LLM failure"],
            )
        return StructuredExtractionResult(
            fields={
                "max_amount": FieldExtraction(value=500.0, confidence=0.95, source=ExtractionSource.TEXT),
                "reimbursement_ratio": FieldExtraction(value=0.8, confidence=0.9, source=ExtractionSource.TEXT),
            },
            overall_confidence=0.92,
            requires_review=False,
            raw_text_snippet=text[:500],
        )


class TestStructuredExtractor:
    def test_extract_success(self):
        extractor = FakeExtractor(should_succeed=True)
        result = extractor.extract("差旅费标准：每天500元，报销比例80%")
        assert result.requires_review is False
        assert result.overall_confidence == 0.92
        assert result.fields["max_amount"].value == 500.0
        assert result.fields["reimbursement_ratio"].value == 0.8

    def test_extract_empty_text(self):
        extractor = FakeExtractor(should_succeed=True)
        result = extractor.extract("")
        assert result.requires_review is True
        assert result.overall_confidence == 0.0
        assert "empty" in result.warnings[0].lower()

    def test_extract_validation_failure_triggers_review(self):
        """When LLM returns invalid data, requires_review should be True."""
        extractor = FakeExtractor(should_succeed=False)
        result = extractor.extract("some policy text")
        assert result.requires_review is True
        assert len(result.warnings) > 0

    def test_validate_against_schema_missing_required(self):
        """Missing required field should fail validation."""
        result = StructuredExtractionResult(
            fields={
                "max_amount": FieldExtraction(value=None, confidence=0.0, source=ExtractionSource.MISSING),
            },
            overall_confidence=0.0,
            requires_review=True,
        )
        assert StructuredExtractor._validate_against_schema(result, EXPENSE_POLICY_SCHEMA) is False

    def test_validate_against_schema_all_required_present(self):
        """All required fields present should pass validation."""
        result = StructuredExtractionResult(
            fields={
                "max_amount": FieldExtraction(value=500.0, confidence=0.9, source=ExtractionSource.TEXT),
                "reimbursement_ratio": FieldExtraction(value=0.8, confidence=0.9, source=ExtractionSource.TEXT),
            },
            overall_confidence=0.9,
            requires_review=False,
        )
        assert StructuredExtractor._validate_against_schema(result, EXPENSE_POLICY_SCHEMA) is True

    def test_empty_result_factory(self):
        result = StructuredExtractor.empty_result("some text", ["Error"])
        assert result.requires_review is True
        assert result.raw_text_snippet == "some text"
        assert result.warnings == ["Error"]
