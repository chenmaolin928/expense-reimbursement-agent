"""PaddleOCR worker — standalone subprocess, zero dependency on main project.

Protocol: JSON one-line per message on stdin/stdout.
  Input:  {"id":"...", "image":{"samples":[...], "height":H, "width":W, "channels":C}}
  Output: {"id":"...", "success":true,  "text":"..."}
          {"id":"...", "success":false, "error":"..."}

Keeps PaddleOCR model loaded across invocations (lazy singleton).
Preprocessing pipeline: grayscale → GaussianBlur → Otsu binarization → 1.5x upscale.
"""

import json
import sys
import traceback

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Lazy PaddleOCR singleton
# ---------------------------------------------------------------------------

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=False)
    return _ocr


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------

def preprocess(flat: list, height: int, width: int, channels: int) -> np.ndarray:
    """Reconstruct numpy array from flat list, then preprocess."""
    arr = np.array(flat, dtype=np.uint8).reshape(height, width, channels)

    # RGB → grayscale  (PyMuPDF pixmaps are RGB)
    if channels >= 3:
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    else:
        gray = arr

    # Denoise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Otsu adaptive binarization
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 1.5x upscale → better small-character recognition
    h, w = binary.shape
    scaled = cv2.resize(binary, (int(w * 1.5), int(h * 1.5)), interpolation=cv2.INTER_CUBIC)

    # PaddleOCR expects 3-channel input
    return cv2.cvtColor(scaled, cv2.COLOR_GRAY2BGR)


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def ocr_on_image(flat: list, height: int, width: int, channels: int) -> str:
    """Preprocess and OCR a single image. Returns concatenated text."""
    img = preprocess(flat, height, width, channels)
    ocr = _get_ocr()
    raw = ocr.ocr(img, cls=True)

    parts: list[str] = []
    if raw:
        for region in raw:
            if not region:
                continue
            for item in region:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    txt = item[1]
                    if isinstance(txt, (list, tuple)):
                        parts.append(str(txt[0]))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            req_id = msg.get("id", "0")
            img = msg["image"]
            text = ocr_on_image(
                img["samples"], img["height"],
                img["width"], img["channels"],
            )
            out = {"id": req_id, "success": True, "text": text}
        except Exception:
            out = {"id": msg.get("id", "0"), "success": False, "error": traceback.format_exc()}

        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
