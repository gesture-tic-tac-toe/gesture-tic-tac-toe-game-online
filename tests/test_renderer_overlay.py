import unittest
from unittest.mock import patch

import pygame

from src.renderer import Renderer


class FaceMeshOverlayTests(unittest.TestCase):
    def setUp(self):
        self.renderer = Renderer.__new__(Renderer)
        self.renderer.screen = pygame.Surface((640, 480))
        self.renderer.W = 640
        self.renderer.H = 480

    @patch("src.renderer.pygame.draw.lines")
    def test_draws_face_outline_eyes_and_lips(self, draw_lines):
        landmarks = [(0.5, 0.5)] * 478
        landmarks[10] = (0.25, 0.2)

        self.renderer.draw_face_mesh(landmarks)

        self.assertEqual(draw_lines.call_count, 5)
        self.assertEqual(draw_lines.call_args_list[0].args[3][0], (160, 96))

    @patch("src.renderer.pygame.draw.lines")
    def test_skips_missing_or_incomplete_face_landmarks(self, draw_lines):
        self.renderer.draw_face_mesh([])
        self.renderer.draw_face_mesh([(0.5, 0.5)] * 467)

        draw_lines.assert_not_called()


if __name__ == "__main__":
    unittest.main()
