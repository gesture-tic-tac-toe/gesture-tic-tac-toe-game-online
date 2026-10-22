"""Hand tracking: MediaPipe wrapper returning plain Python hand objects.

Supports BOTH MediaPipe APIs:
  * legacy  mp.solutions.hands   (mediapipe <= ~0.10.21, model bundled, no download)
  * tasks   HandLandmarker       (newer releases; needs assets/models/hand_landmarker.task,
                                   which is downloaded automatically on first start)
"""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from typing import List, Tuple

import cv2

from .config import MODEL_DIR

Point = Tuple[float, float]

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH = MODEL_DIR / "hand_landmarker.task"

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
    (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18),
    (18, 19), (19, 20), (0, 17),
]


@dataclass
class HandInfo:
    landmarks: List[Point]          # 21 normalised (x, y) points, already mirrored like the preview

    @property
    def tip(self) -> Point:         # index fingertip = pointer
        return self.landmarks[8]

    @property
    def wrist(self) -> Point:
        return self.landmarks[0]


class HandTracker:
    def __init__(self, max_hands: int = 2, detect_conf: float = 0.6, track_conf: float = 0.5) -> None:
        import mediapipe as mp
        self._mp = mp
        self._legacy = hasattr(mp, "solutions") and hasattr(mp.solutions, "hands")
        self._ts = 0
        if self._legacy:
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=max_hands, model_complexity=0,
                min_detection_confidence=detect_conf, min_tracking_confidence=track_conf)
        else:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
            self._ensure_model()
            options = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=max_hands,
                min_hand_detection_confidence=detect_conf,
                min_hand_presence_confidence=track_conf,
                min_tracking_confidence=track_conf)
            self._landmarker = vision.HandLandmarker.create_from_options(options)

    @staticmethod
    def _ensure_model() -> None:
        if MODEL_PATH.exists():
            return
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading hand model to {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

    def process(self, frame_bgr) -> List[HandInfo]:
        """Detect hands in a BGR frame. Never raises - returns [] on any failure."""
        if frame_bgr is None:
            return []
        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            if self._legacy:
                rgb.flags.writeable = False
                result = self._hands.process(rgb)
                raw = [[(p.x, p.y) for p in h.landmark] for h in (result.multi_hand_landmarks or [])]
            else:
                self._ts += 33                       # monotonically increasing ms timestamp
                image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
                result = self._landmarker.detect_for_video(image, self._ts)
                raw = [[(p.x, p.y) for p in h] for h in result.hand_landmarks]
        except Exception as exc:                     # temporary detection failure must not crash
            print("hand tracking error:", exc)
            return []
        hands = [HandInfo(pts) for pts in raw if len(pts) == 21]
        hands.sort(key=lambda h: h.wrist[0])         # stable order: left -> right
        return hands

    def close(self) -> None:
        try:
            if self._legacy:
                self._hands.close()
            else:
                self._landmarker.close()
        except Exception:
            pass
