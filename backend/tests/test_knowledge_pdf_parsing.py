"""Regression tests for knowledge PDF text extraction."""

from __future__ import annotations

import sys
import types

from app.api.knowledge import _extract_text, _is_garbled


def test_is_garbled_detects_null_byte_style_pdf_mojibake() -> None:
    """Chinese PDF mojibake often contains null bytes and sparse high-byte chars."""
    text = "\x00N\x00-e\x87u\x00f\x10v"

    assert _is_garbled(text) is True


def test_pdf_uses_ocr_strategy(monkeypatch) -> None:
    """PDF files should use OCR strategy, not text layer extraction."""

    from app.api.knowledge import _extract_text, _SUPPORTED_EXTENSIONS

    # Verify PDF is configured for OCR only
    assert _SUPPORTED_EXTENSIONS[".pdf"] == ["ocr"]

    # Mock PyMuPDF (fitz) to return a fake page image
    fitz_module = types.ModuleType("fitz")

    class _FakePixmap:
        samples = b"\x00" * (100 * 100 * 3)  # 100x100 RGB
        height = 100
        width = 100
        n = 3

    class _FakePage:
        def get_pixmap(self, dpi=200):
            return _FakePixmap()

    class _FakeDoc:
        def __init__(self, stream, filetype):
            self._pages = [_FakePage()]
        def __iter__(self):
            return iter(self._pages)
        def close(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    fitz_module.open = _FakeDoc
    monkeypatch.setitem(sys.modules, "fitz", fitz_module)

    # Mock easyocr to return known text
    easyocr_module = types.ModuleType("easyocr")

    class _FakeReader:
        def __init__(self, langs, gpu=True):
            pass
        def readtext(self, img_array, detail=0):
            return ["差旅报销政策：餐补上限 100 元。"]

    easyocr_module.Reader = _FakeReader
    monkeypatch.setitem(sys.modules, "easyocr", easyocr_module)

    # Mock numpy (easyocr internally uses numpy.frombuffer)
    np_module = types.ModuleType("numpy")
    np_module.uint8 = type("uint8", (), {})
    np_module.frombuffer = lambda buffer, dtype: type("ndarray", (), {
        "reshape": lambda self, h, w, n: self,
    })()
    monkeypatch.setitem(sys.modules, "numpy", np_module)

    extracted = _extract_text("policy.pdf", b"%PDF-1.4 fake")

    assert extracted == "差旅报销政策：餐补上限 100 元。"
