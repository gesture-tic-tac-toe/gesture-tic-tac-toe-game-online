import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pygame
from main import App
from src.gesture_detector import HoldDetector


class MenuClickTests(unittest.TestCase):
    def make_app(self):
        app = App.__new__(App)
        app.cfg = SimpleNamespace(window_size=(800, 600))
        app.mouse_pos = None
        app.mouse_time = -99.0
        app.hands = []
        app.smoother = Mock()
        app.smoother.update.return_value = (150, 150)
        app.frozen_pos = None
        app.click_hold = HoldDetector(0.01)
        app.buttons = [
            SimpleNamespace(id="play_ai", rect=SimpleNamespace(
                collidepoint=lambda pos: pos == (150, 150)))
        ]
        app.audio = SimpleNamespace(play=Mock())
        app.activate = Mock()
        return app

    def test_middle_pinch_clicks_hovered_button_while_mouse_cursor_is_active(self):
        app = App.__new__(App)
        app.cfg = SimpleNamespace(window_size=(800, 600))
        app.mouse_pos = (150, 150)
        app.mouse_time = 9.9
        landmarks = [(0.5, 0.9)] * 21
        landmarks[9] = (0.5, 0.6)
        landmarks[4] = (0.55, 0.3)
        landmarks[12] = (0.56, 0.31)
        app.hands = [SimpleNamespace(landmarks=landmarks)]
        app.smoother = Mock()
        app.frozen_pos = None
        app.click_hold = HoldDetector(0.01)
        app.buttons = [
            SimpleNamespace(id="play_ai", rect=SimpleNamespace(
                collidepoint=lambda pos: pos == (150, 150)))
        ]
        app.audio = SimpleNamespace(play=Mock())
        app.activate = Mock()

        app.update_ui(10.0)
        app.update_ui(10.02)
        app.update_ui(10.04)

        app.activate.assert_called_once_with("play_ai", 10.02)
        app.audio.play.assert_called_once_with("place")

    def test_hovering_without_pinch_does_not_activate_button(self):
        app = self.make_app()

        for now in (10.0, 11.0, 12.0):
            app.update_ui(now)

        app.activate.assert_not_called()
        app.audio.play.assert_not_called()

    @patch("main.pygame.event.get")
    def test_mouse_button_click_does_not_activate_button(self, get_events):
        app = self.make_app()
        app.game = SimpleNamespace()
        app.running = True
        get_events.return_value = [
            SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(150, 150))
        ]

        app.handle_events(10.0)

        app.activate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
