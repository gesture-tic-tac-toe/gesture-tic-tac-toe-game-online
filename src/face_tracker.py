"""Face tracker: only used to read how open each eye is (for the WINK = exit gesture).

Like the hand tracker it supports BOTH MediaPipe APIs:
  * legacy  mp.solutions.face_mesh  (mediapipe <= ~0.10.21, model bundled)
  * tasks   FaceLandmarker          (newer releases; needs assets/models/face_landmarker.task,
                                      downloaded automatically on first use)
Nothing is stored - only two numbers per frame leave this module.
"""
from __future__ import annotations

import urllib.request
from typing import List, Optional, Tuple

import cv2

from .config import MODEL_DIR
from .gesture_detector import eye_aspect_ratio

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
             "face_landmarker/float16/1/face_landmarker.task")
MODEL_PATH = MODEL_DIR / "face_landmarker.task"

# MediaPipe face-mesh indices: corner, upper, upper, corner, lower, lower
EYE_IMAGE_LEFT = (33, 160, 158, 133, 153, 144)       # left side of the picture
EYE_IMAGE_RIGHT = (362, 385, 387, 263, 373, 380)     # right side of the picture


class FaceTracker:
    def __init__(self) -> None:
        import mediapipe as mp
        self._mp = mp
        self._legacy = hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh")
        self._ts = 0
        self.landmarks: List[Tuple[float, float]] = []
        if self._legacy:
            self._mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False, max_num_faces=1, refine_landmarks=True,   # refined eyelids = reliable wink
                min_detection_confidence=0.5, min_tracking_confidence=0.5)
        else:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
            self._ensure_model()
            options = vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO, num_faces=1,
                min_face_detection_confidence=0.5, min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5)
            self._landmarker = vision.FaceLandmarker.create_from_options(options)

    @staticmethod
    def _ensure_model() -> None:
        if MODEL_PATH.exists():
            return
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading face model to {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

    def process(self, frame_bgr) -> Optional[Tuple[float, float]]:
        """(eye openness left-of-picture, right-of-picture) or None when no face is visible.
        Never raises."""
        if frame_bgr is None:
            self.landmarks = []
            return None
        try:
            h, w = frame_bgr.shape[:2]
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            if self._legacy:
                rgb.flags.writeable = False
                result = self._mesh.process(rgb)
                faces = [[(p.x, p.y) for p in f.landmark] for f in (result.multi_face_landmarks or [])]
            else:
                self._ts += 66
                image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
                result = self._landmarker.detect_for_video(image, self._ts)
                faces = [[(p.x, p.y) for p in f] for f in result.face_landmarks]
            if not faces or len(faces[0]) < 468:   # (refined mesh has 478 points)
                self.landmarks = []
                return None
            self.landmarks = faces[0]
            px = [(x * w, y * h) for x, y in faces[0]]      # pixels, so the ratio is not distorted
            return (eye_aspect_ratio([px[i] for i in EYE_IMAGE_LEFT]),
                    eye_aspect_ratio([px[i] for i in EYE_IMAGE_RIGHT]))
        except Exception as exc:
            self.landmarks = []
            print("face tracking error:", exc)
            return None

    def close(self) -> None:
        try:
            (self._mesh if self._legacy else self._landmarker).close()
        except Exception:
            pass
