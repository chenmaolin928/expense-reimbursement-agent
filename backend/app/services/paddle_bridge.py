"""Bridge to PaddleOCR worker — subprocess-based, zero dependency on PaddlePaddle libs.

Architecture:
  - Launches paddle_ocr_worker/worker.py as a persistent subprocess
  - Communicates via JSON-lines stdin/stdout (one line = one request/response)
  - Auto-restarts on crash; keeps model warm across calls
  - Thread-safe for concurrent callers

Usage:
    bridge = PaddleBridge(venv_dir="./paddle_ocr_worker/venv")
    text = bridge.ocr_bytes(img_bytes)    # from raw image bytes
    text = bridge.ocr_numpy(np_array)     # from numpy HWC array
    bridge.shutdown()
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from typing import Any


class PaddleBridge:
    """Subprocess bridge to isolated PaddleOCR worker."""

    _counter = 0
    _lock = threading.Lock()

    def __init__(self, venv_dir: str | None = None) -> None:
        self._venv_dir = venv_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "paddle_ocr_worker", "venv",
        )
        self._proc: subprocess.Popen | None = None
        self._buf: str = ""
        self._cv = threading.Condition(self._lock)
        self._callbacks: dict[str, Any] = {}
        self._reader_thread: threading.Thread | None = None
        self._shutdown_flag = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ocr_bytes(self, image_bytes: bytes, ext: str = ".png") -> str:
        """OCR a raw image (PNG/JPEG) encoded in memory."""
        import cv2
        import numpy as np

        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            return ""
        # OpenCV decodes as BGR → convert to RGB (matching PyMuPDF pixmap order)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return self._send(img_rgb)

    def ocr_pixmap(self, samples: bytes, height: int, width: int, channels: int = 3) -> str:
        """OCR a PyMuPDF pixmap directly — avoids decode/encode round-trip."""
        import numpy as np

        arr = np.frombuffer(samples, dtype=np.uint8).reshape(height, width, channels)
        return self._send(arr)

    def shutdown(self) -> None:
        """Terminate the worker subprocess."""
        with self._lock:
            self._shutdown_flag = True
            if self._proc:
                self._proc.terminate()
                self._proc = None
            self._callbacks.clear()
            self._cv.notify_all()

    # ------------------------------------------------------------------
    # Subprocess lifecycle
    # ------------------------------------------------------------------

    def _ensure_proc(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        # Locate worker.py
        worker_py = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "paddle_ocr_worker", "worker.py",
        )
        worker_py = os.path.abspath(worker_py)

        # Determine python executable from venv
        if os.name == "nt":
            python_exe = os.path.join(self._venv_dir, "Scripts", "python.exe")
        else:
            python_exe = os.path.join(self._venv_dir, "bin", "python")

        if not os.path.exists(python_exe):
            raise RuntimeError(
                f"PaddleOCR venv not found at {self._venv_dir}. "
                f"Run: python -m venv {self._venv_dir} && "
                f"{python_exe} -m pip install -r {os.path.dirname(worker_py)}/requirements.txt "
                f"-f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html"
            )

        self._proc = subprocess.Popen(
            [python_exe, "-u", worker_py],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered
        )
        self._buf = ""
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True,
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        """Background thread: read lines from worker stdout."""
        assert self._proc is not None and self._proc.stdout is not None
        while not self._shutdown_flag:
            try:
                line = self._proc.stdout.readline()
            except (ValueError, OSError):
                break
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                resp = {"id": "0", "success": False, "error": f"malformed: {line}"}

            msg_id = resp.get("id", "0")
            with self._lock:
                cb = self._callbacks.pop(msg_id, None)
                if cb:
                    cb["result"] = resp
                    self._cv.notify_all()

    def _send(self, img_arr: "Any") -> str:
        """Send a numpy image to the worker and wait for the result."""
        import numpy as np

        if not isinstance(img_arr, np.ndarray):
            return ""

        h, w = img_arr.shape[:2]
        c = img_arr.shape[2] if img_arr.ndim == 3 else 1

        with self._lock:
            self._ensure_proc()
            req_id = str(self._counter)
            self._counter += 1
            event = {"result": None}
            self._callbacks[req_id] = event

        req = json.dumps({
            "id": req_id,
            "image": {
                "samples": img_arr.flatten().tolist(),
                "height": h,
                "width": w,
                "channels": c,
            },
        }, ensure_ascii=False)

        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(req + "\n")
        self._proc.stdin.flush()

        with self._lock:
            self._cv.wait_for(lambda: event["result"] is not None, timeout=120.0)
            resp = event["result"]
            if resp is None:
                return ""
            if not resp.get("success"):
                return ""
            return resp.get("text", "")
