"""Text quality assessment — quality scoring and routing recommendation for document parsing.

Architecture (see docs/superpowers/specs/2026-07-02-architecture-refactoring-design.md):

    Upload → Text Extraction → TextQualityAssessor → Three-way routing:
      - confidence ≥ 0.7 → direct LLM extraction
      - 0.3 < confidence < 0.7 → OCR + merge
      - confidence ≤ 0.3 → force OCR
"""

import re
from dataclasses import dataclass


@dataclass
class QualityAssessment:
    """Assessment result for a text fragment.

    Attributes:
        confidence: Overall quality score [0.0, 1.0].
        char_count: Number of printable characters.
        garbled_ratio: Ratio of non-printable / non-CJK characters.
        avg_line_length: Average length of non-empty lines.
        has_text_layer: Whether the source had an extractable text layer.
        recommendation: Routing decision — "direct_llm", "ocr_merge", or "force_ocr".
    """
    confidence: float
    char_count: int
    garbled_ratio: float
    avg_line_length: float
    has_text_layer: bool
    recommendation: str


class TextQualityAssessor:
    """Assesses text quality and recommends the optimal extraction path.

    The assessor evaluates three signals:
      1. Character count (meaningful content length).
      2. Garbled ratio (non-printable / exotic Unicode vs normal text).
      3. Average line length (short lines often indicate OCR artifacts).

    Routing thresholds are documented in the architecture spec.
    """

    # Characters considered "normal" — ASCII printable, CJK unified ideographs,
    # CJK symbols and punctuation, fullwidth forms, common whitespace.
    # NOTE: U+FFFD (�) is the Unicode REPLACEMENT CHARACTER — it is NOT normal.
    NORMAL_PATTERN = re.compile(
        r'[\x20-\x7E'           # ASCII printable
        r'一-鿿'         # CJK Unified Ideographs
        r'　-￿'          # CJK Symbols and Punctuation, Fullwidth Forms
        r'\n\r\t'                # Common whitespace
        r']'
    )

    # Characters that *are not* normal — used to detect garbled content.
    # Also explicitly includes the replacement character U+FFFD.
    GARBLED_PATTERN = re.compile(
        r'[^\x20-\x7E'
        r'一-鿿'
        r'　-￿'
        r'\n\r\t'
        r']'
        r'|�'
    )

    # Minimum meaningful content to skip direct OCR (50 CJK chars ≈ 2-3 sentences)
    MIN_CHARS_FOR_DIRECT_LLM = 50

    # Below this garbled ratio the text is considered clean enough for direct LLM.
    DIRECT_LLM_GARBLED_THRESHOLD = 0.15

    # Below this garbled ratio OCR merge may help; above it force OCR.
    OCR_MERGE_GARBLED_THRESHOLD = 0.30

    def assess(self, text: str) -> QualityAssessment:
        if not text or not text.strip():
            return QualityAssessment(
                confidence=0.0,
                char_count=0,
                garbled_ratio=1.0,
                avg_line_length=0.0,
                has_text_layer=False,
                recommendation="force_ocr",
            )

        text_stripped = text.strip()
        char_count = len(text_stripped)
        garbled_chars = len(self.GARBLED_PATTERN.findall(text_stripped))
        garbled_ratio = garbled_chars / max(char_count, 1)

        lines = [l for l in text_stripped.split('\n') if l.strip()]
        avg_line_length = sum(len(l) for l in lines) / max(len(lines), 1)

        # Decision tree (see architecture spec §3.2)
        if char_count > self.MIN_CHARS_FOR_DIRECT_LLM and garbled_ratio < self.DIRECT_LLM_GARBLED_THRESHOLD:
            confidence = min(1.0, (char_count / 500) * (1.0 - garbled_ratio))
            return QualityAssessment(
                confidence=round(confidence, 4),
                char_count=char_count,
                garbled_ratio=round(garbled_ratio, 4),
                avg_line_length=round(avg_line_length, 2),
                has_text_layer=True,
                recommendation="direct_llm",
            )

        if char_count > self.MIN_CHARS_FOR_DIRECT_LLM and garbled_ratio < self.OCR_MERGE_GARBLED_THRESHOLD:
            return QualityAssessment(
                confidence=0.5,
                char_count=char_count,
                garbled_ratio=round(garbled_ratio, 4),
                avg_line_length=round(avg_line_length, 2),
                has_text_layer=True,
                recommendation="ocr_merge",
            )

        return QualityAssessment(
            confidence=0.0,
            char_count=char_count,
            garbled_ratio=round(garbled_ratio, 4),
            avg_line_length=round(avg_line_length, 2),
            has_text_layer=char_count > 0,
            recommendation="force_ocr",
        )
