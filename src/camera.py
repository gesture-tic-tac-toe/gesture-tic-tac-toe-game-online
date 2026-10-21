"""Camera manager: webcam capture + mirroring."""
from __future__ import annotations

import sys
from typing import Optional

import cv2
import numpy as np

from .config import Config


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.cap: Optional[cv2.VideoCapture] = None

    def open(self) -> None:
        self.release()
        backends = [cv2.CAP_ANY]
        if sys.platform.startswith("win"):
            backends.insert(0, cv2.CAP_DSHOW)       # faster / more reliable on Windows
        for backend in backends:
            cap = cv2.VideoCapture(self.cfg.camera_index, backend)
            if cap.isOpened():
                w, h = self.cfg.camera_size
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # keep latency low (ignored by some drivers)
                ok, _ = cap.read()
                if ok:
                    self.cap = cap
                    return
            cap.release()
        raise CameraError(
            f"No webcam found at index {self.cfg.camera_index}.\n"
            "Plug in a camera, close other apps that use it, then press R to retry."
        )

    def read(self) -> Optional[np.ndarray]:
        """Returns a BGR frame (mirrored if configured) or None on a failed read."""
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        return cv2.flip(frame, 1) if self.cfg.mirror else frame

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
