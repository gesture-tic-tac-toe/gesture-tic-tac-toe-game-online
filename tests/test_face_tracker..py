import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from src.face_tracker import FaceTracker


class FaceTrackerLandmarkTests(unittest.TestCase):
    def setUp(self):
        self.tracker = FaceTracker.__new__(FaceTracker)
        self.tracker._legacy = True
        self.tracker._mesh = Mock()
        self.tracker.landmarks = [(0.1, 0.1)]
        points = [SimpleNamespace(x=0.5, y=0.4) for _ in range(478)]
        self.tracker._mesh.process.return_value = SimpleNamespace(
            multi_face_landmarks=[SimpleNamespace(landmark=points)]
        )

    def test_process_exposes_normalized_face_landmarks_for_overlay(self):
        eyes = self.tracker.process(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertIsNotNone(eyes)
        self.assertEqual(len(self.tracker.landmarks), 478)
        self.assertEqual(self.tracker.landmarks[0], (0.5, 0.4))

    def test_missing_face_clears_landmarks(self):
        self.tracker._mesh.process.return_value = SimpleNamespace(multi_face_landmarks=[])

        self.assertIsNone(self.tracker.process(np.zeros((100, 200, 3), dtype=np.uint8)))
        self.assertEqual(self.tracker.landmarks, [])


if __name__ == "__main__":
    unittest.main()
