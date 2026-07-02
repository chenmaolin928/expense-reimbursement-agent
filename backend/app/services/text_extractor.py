"""Shared text extraction — PDF, DOCX, TXT, OCR via isolated subprocess.

Extracted from `app.api.knowledge` so both knowledge-base uploads and
policy uploads use the same text-extraction pipeline.
"""

from __future__ import annotations

import threading
import unicodedata
from io import BytesIO
from typing import Optional

# ---------------------------------------------------------------------------
# Supported file types
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS: dict[str, list[str]] = {
    ".txt": ["text"],
    ".docx": ["text"],
    ".pdf": ["text", "ocr"],  # text layer first, OCR fallback
}


def get_extraction_strategies(filename: str) -> list[str]:
    """Return the ordered list of extraction strategies based on file extension."""
    from fastapi import HTTPException

    lower = filename.lower()
    for ext, strategies in _SUPPORTED_EXTENSIONS.items():
        if lower.endswith(ext):
            return strategies
    raise HTTPException(
        status_code=400,
        detail=f"不支持的文件类型: {filename}。支持的类型: .txt, .docx, .pdf",
    )


# ---------------------------------------------------------------------------
# Garbled-text heuristic
# ---------------------------------------------------------------------------

REPLACEMENT_CHAR = "�"


def is_garbled(text: str) -> bool:
    """Heuristic: text is likely garbled if it has high-byte chars but no CJK characters."""
    stripped = text.strip()
    if not stripped:
        return True

    visible_chars = [c for c in stripped if not c.isspace()]
    if not visible_chars:
        return True

    total = len(visible_chars)
    high_byte = sum(1 for c in visible_chars if ord(c) > 127)
    cjk = sum(1 for c in visible_chars if "一" <= c <= "鿿" or "㐀" <= c <= "䶿")
    control_chars = sum(
        1
        for c in visible_chars
        if unicodedata.category(c).startswith("C") and c not in "\n\r\t\f"
    )
    replacement_chars = stripped.count(REPLACEMENT_CHAR)

    # Hard garbled markers
    if control_chars > 0 or replacement_chars > 0:
        return True

    cjk_ratio = cjk / total
    if cjk_ratio >= 0.2:
        return False

    if cjk > 0:
        return high_byte > 5 or (high_byte > 0 and high_byte / total > 0.3)

    return high_byte > 5 or (high_byte > 0 and high_byte / max(total, 1) > 0.3)


# ---------------------------------------------------------------------------
# Text layer extraction  (PDF / DOCX / TXT)
# ---------------------------------------------------------------------------


def extract_text_layer(filename: str, content_bytes: bytes) -> str | None:
    """Extract text from text-based files (PDF text layer, DOCX, TXT).

    Returns None if extraction fails.
    """
    lower = filename.lower()

    # PDF text layer: extract with fitz (PyMuPDF) get_text("text")
    if lower.endswith(".pdf"):
        try:
            import fitz

            doc = fitz.open(stream=content_bytes, filetype="pdf")
            pages_text = [page.get_text("text").strip() for page in doc]
            doc.close()
            full_text = "\n".join(p.strip() for p in pages_text if p.strip())
            return full_text if full_text else None
        except Exception:
            return None

    # Word .docx: extract with python-docx
    if lower.endswith(".docx"):
        try:
            from docx import Document

            doc = Document(BytesIO(content_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs).strip()
            return text if text else None
        except Exception:
            return None

    # Plain text: detect encoding with chardet
    import chardet

    detected = chardet.detect(content_bytes)
    encoding = detected.get("encoding") or "utf-8"
    confidence = detected.get("confidence", 0)

    single_byte_encodings = {
        "iso-8859-1",
        "iso-8859-2",
        "iso-8859-5",
        "iso-8859-9",
        "windows-1252",
        "windows-1250",
        "windows-1251",
        "windows-1254",
        "mac_roman",
        "latin-1",
        "latin1",
        "tis-620",
    }

    if confidence < 0.6 or encoding.lower() in single_byte_encodings:
        for fb in ("gb18030", "gbk", "gb2312", "utf-8"):
            try:
                decoded = content_bytes.decode(fb)
                if not is_garbled(decoded):
                    return decoded
            except (UnicodeDecodeError, LookupError):
                continue

    try:
        decoded = content_bytes.decode(encoding)
        if not is_garbled(decoded):
            return decoded
    except (UnicodeDecodeError, LookupError):
        pass

    for fallback in ("utf-8", "gbk", "gb2312", "gb18030"):
        try:
            decoded = content_bytes.decode(fallback)
            if not is_garbled(decoded):
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue

    return None


# ---------------------------------------------------------------------------
# OCR extraction  (PaddleBridge singleton)
# ---------------------------------------------------------------------------

_ocr_bridge = None
_ocr_bridge_lock = threading.Lock()


def _get_ocr_bridge():
    """Return the shared PaddleBridge instance (lazy singleton)."""
    from app.services.paddle_bridge import PaddleBridge

    global _ocr_bridge
    if _ocr_bridge is None:
        with _ocr_bridge_lock:
            if _ocr_bridge is None:
                _ocr_bridge = PaddleBridge()
    return _ocr_bridge


def ocr_extract(filename: str, content_bytes: bytes) -> str | None:
    """Extract text from image-based files via OCR subprocess bridge.

    Currently only supports PDF (renders each page → OCR).  Image-only
    files (JPEG, PNG, …) are not yet handled at this level.
    """
    lower = filename.lower()

    if lower.endswith(".pdf"):
        try:
            import fitz
            import numpy as np

            bridge = _get_ocr_bridge()
            doc = fitz.open(stream=content_bytes, filetype="pdf")
            pages_text: list[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=400)
                text = bridge.ocr_pixmap(pix.samples, pix.height, pix.width, pix.n)
                if text:
                    pages_text.append(text)
            doc.close()

            full_text = "\n".join(pages_text).strip()
            return full_text if full_text and not is_garbled(full_text) else None
        except Exception:
            return None

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def extract_text(
    filename: str, content_bytes: bytes, *, assessor: Optional[object] = None
) -> tuple[str, dict]:
    """Extract text from uploaded file with quality assessment and routing.

    Returns (text, metadata) where metadata includes processing_chain
    and quality_assessment dict.

    Args:
        filename: Original uploaded filename (used to infer type).
        content_bytes: Raw file bytes.
        assessor: Optional TextQualityAssessor instance.  If None, quality
            assessment is skipped (metadata contains basic info only).
    """
    from app.services.text_quality_assessor import TextQualityAssessor

    strategies = get_extraction_strategies(filename)
    assessor = assessor or TextQualityAssessor()

    first_result: str | None = None
    first_quality = None

    for strategy in strategies:
        if strategy == "text":
            result = extract_text_layer(filename, content_bytes)
        elif strategy == "ocr":
            result = ocr_extract(filename, content_bytes)
        else:
            continue

        if not result:
            continue

        quality = assessor.assess(result)
        if first_result is None:
            first_result = result
            first_quality = quality

        # OCR output that contains CJK characters is accepted directly
        if strategy == "ocr" and any("一" <= c <= "鿿" for c in result):
            return result, {
                "processing_chain": "ocr_extract",
                "quality_assessment": {
                    "confidence": quality.confidence,
                    "char_count": quality.char_count,
                    "garbled_ratio": quality.garbled_ratio,
                    "recommendation": "force_ocr",
                },
            }

        # High quality → accept immediately
        if quality.recommendation == "direct_llm":
            return result, {
                "processing_chain": "text_layer_direct",
                "quality_assessment": {
                    "confidence": quality.confidence,
                    "char_count": quality.char_count,
                    "garbled_ratio": quality.garbled_ratio,
                    "recommendation": "direct_llm",
                },
            }

        # Medium quality with more strategies available → try next
        if quality.recommendation == "ocr_merge" and strategy == "text":
            continue

        if quality.recommendation == "force_ocr":
            continue

    # All strategies exhausted → raise error if result is still garbled
    if first_result and first_quality:
        if first_quality.recommendation in ("direct_llm",):
            return first_result, {
                "processing_chain": "fallback",
                "quality_assessment": {
                    "confidence": first_quality.confidence,
                    "char_count": first_quality.char_count,
                    "garbled_ratio": first_quality.garbled_ratio,
                    "recommendation": "fallback",
                },
            }
        # For "ocr_merge" or "force_ocr" recommendations, OCR should have fixed it
        # but didn't → the file is likely a scanned image PDF without OCR available.
        # Raise a clear error instead of passing garbled text to the LLM.
        from fastapi import HTTPException

        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "unknown"
        if ext in ("pdf",):
            detail = (
                "该PDF无法提取有效文本（可能是扫描件且OCR不可用）。"
                "请上传带可选文本层的PDF，或粘贴文本为.txt文件。"
            )
        else:
            detail = (
                f"无法从{ext.upper()}文件中提取有效文本。"
                "请确保文件编码为UTF-8或GBK格式，或尝试粘贴文本内容。"
            )
        raise HTTPException(status_code=400, detail=detail)

    from fastapi import HTTPException

    raise HTTPException(
        status_code=400,
        detail="无法从文件中提取有效文本。该文件可能是扫描件或图片型PDF，请尝试："
               "1) 将内容复制到.txt文件后上传；"
               "2) 使用带可选文本层的PDF。",
    )
