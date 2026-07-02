"""Regression tests for knowledge PDF text extraction."""
from __future__ import annotations

import sys
import types

import pytest

from app.api.knowledge import _extract_text, _is_garbled, _SUPPORTED_EXTENSIONS


@pytest.fixture(autouse=True)
def _reset_bridge():
    """Reset the module-level bridge singleton before each test."""
    import app.api.knowledge
    app.api.knowledge._ocr_bridge = None
    yield


def test_is_garbled_detects_null_byte_style_pdf_mojibake() -> None:
    """Chinese PDF mojibake often contains null bytes and sparse high-byte chars."""
    text = "\x00N\x00-e\x87u\x00f\x10v"

    assert _is_garbled(text) is True


def test_pdf_strategies_text_first() -> None:
    """PDF should use text layer extraction first, then OCR fallback."""
    assert _SUPPORTED_EXTENSIONS[".pdf"] == ["text", "ocr"]


def test_text_layer_pdf_extraction(monkeypatch) -> None:
    """PDF with readable text layer should extract via fitz get_text()."""
    fitz_module = types.ModuleType("fitz")

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

    class _FakePage:
        def get_text(self, mode: str) -> str:
            return "差旅报销政策：餐补上限 100 元。出差住宿标准为 500 元/晚。"
        def get_pixmap(self, dpi=400):
            raise RuntimeError("Should not reach pixmap rendering in text-layer path")

    fitz_module.open = _FakeDoc
    monkeypatch.setitem(sys.modules, "fitz", fitz_module)

    extracted = _extract_text("policy.pdf", b"%PDF-1.4 fake content")
    text = extracted if isinstance(extracted, str) else extracted[0]
    assert "差旅报销政策" in text
    assert "餐补上限" in text


def test_ocr_fallback_when_text_layer_garbled(monkeypatch) -> None:
    """PDF with garbled text layer should fall back to OCR."""
    fitz_module = types.ModuleType("fitz")

    class _FakeGarbledPage:
        def get_text(self, mode: str) -> str:
            return "\x00N\x00-e\x87u\x00f\x10v garbled"
        def get_pixmap(self, dpi=400):
            return _FakePixmap()

    class _FakePixmap:
        samples = b"\x00" * (100 * 100 * 3)  # 100x100 RGB
        height = 100
        width = 100
        n = 3

    class _FakeDoc:
        def __init__(self, stream, filetype):
            self._pages = [_FakeGarbledPage()]
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

    # Mock PaddleBridge
    bridge_module = types.ModuleType("app.services.paddle_bridge")
    class _FakeBridge:
        def ocr_pixmap(self, samples, height, width, channels):
            return "差旅报销政策：餐补上限 100 元。"
        def shutdown(self):
            pass
    class _FakeBridgeClass:
        def __init__(self, venv_dir=None):
            pass
    bridge_module.PaddleBridge = _FakeBridgeClass
    monkeypatch.setitem(sys.modules, "app.services.paddle_bridge", bridge_module)

    # Replace the bridge singleton so _get_ocr_bridge returns our fake
    import app.api.knowledge
    app.api.knowledge._ocr_bridge = _FakeBridge()

    extracted = _extract_text("policy.pdf", b"%PDF-1.4 fake")
    text = extracted if isinstance(extracted, str) else extracted[0]
    assert "差旅报销政策" in text
    assert "餐补上限" in text


def test_ocr_fallback_when_pdf_no_text_layer(monkeypatch) -> None:
    """Scanned PDF with no text layer should use OCR path directly."""
    fitz_module = types.ModuleType("fitz")

    class _FakeEmptyPage:
        def get_text(self, mode: str) -> str:
            return ""  # empty text layer (scanned document)
        def get_pixmap(self, dpi=400):
            return _FakePixmap()

    class _FakePixmap:
        samples = b"\x00" * (100 * 100 * 3)
        height = 100
        width = 100
        n = 3

    class _FakeDoc:
        def __init__(self, stream, filetype):
            self._pages = [_FakeEmptyPage()]
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

    # Mock PaddleBridge
    bridge_module = types.ModuleType("app.services.paddle_bridge")
    class _FakeBridge:
        def ocr_pixmap(self, samples, height, width, channels):
            return "扫描文档内容"
        def shutdown(self):
            pass
    class _FakeBridgeClass:
        def __init__(self, venv_dir=None):
            pass
    bridge_module.PaddleBridge = _FakeBridgeClass
    monkeypatch.setitem(sys.modules, "app.services.paddle_bridge", bridge_module)

    import app.api.knowledge
    app.api.knowledge._ocr_bridge = _FakeBridge()

    extracted = _extract_text("policy.pdf", b"%PDF-1.4 fake")
    text = extracted if isinstance(extracted, str) else extracted[0]
    assert "扫描文档内容" in text
