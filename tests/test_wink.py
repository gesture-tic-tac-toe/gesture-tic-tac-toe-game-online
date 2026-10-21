import unittest

from src.gesture_detector import (CLOSED_EAR, OPEN_EAR, WinkDetector, eye_aspect_ratio, is_wink)


def eye(opening):
    """Six eye points: corners 1.0 apart, lids `opening` apart."""
    h = opening / 2
    return [(0.0, 0.0), (0.3, -h), (0.7, -h), (1.0, 0.0), (0.7, h), (0.3, h)]


class EyeRatioTests(unittest.TestCase):
    def test_open_and_closed(self):
        self.assertAlmostEqual(eye_aspect_ratio(eye(0.30)), 0.30, places=3)
        self.assertLess(eye_aspect_ratio(eye(0.02)), CLOSED_EAR)
        self.assertGreater(eye_aspect_ratio(eye(0.25)), OPEN_EAR)

    def test_degenerate_eye_does_not_crash(self):
        self.assertEqual(eye_aspect_ratio([(0, 0)] * 6), 0.0)


class IsWinkTests(unittest.TestCase):
    def test_one_eye_closed_is_a_wink_either_side(self):
        self.assertTrue(is_wink((0.023, 0.236)))            # values measured on the reference photo
        self.assertTrue(is_wink((0.236, 0.023)))

    def test_both_open_or_both_closed_is_not(self):
        self.assertFalse(is_wink((0.25, 0.25)))              # normal face
        self.assertFalse(is_wink((0.03, 0.04)))              # blink / eyes shut

    def test_squint_and_missing_face(self):
        self.assertFalse(is_wink((0.15, 0.25)))              # half-closed eye is not a wink
        self.assertFalse(is_wink(None))


class WinkDetectorTests(unittest.TestCase):
    WINK, OPEN = (0.02, 0.24), (0.24, 0.24)

    def run_for(self, det, ears, start, seconds, step=0.05):
        t, out = start, (0.0, False)
        while t <= start + seconds + 1e-9:
            out = det.update(ears, t)
            if out[1]:
                return t, out
            t += step
        return t, out

    def test_fires_after_hold_only_once(self):
        det = WinkDetector(hold=1.0)
        t, (progress, fired) = self.run_for(det, self.WINK, 0.0, 1.5)
        self.assertTrue(fired)
        self.assertAlmostEqual(t, 1.0, delta=0.06)
        _, (_, again) = self.run_for(det, self.WINK, t + 0.05, 2.0)
        self.assertFalse(again)                              # must release before it can fire again

    def test_blink_does_not_fire(self):
        det = WinkDetector(hold=1.0)
        _, (_, fired) = self.run_for(det, (0.03, 0.03), 0.0, 3.0)    # both eyes shut for 3 s
        self.assertFalse(fired)

    def test_short_wink_resets(self):
        det = WinkDetector(hold=1.0)
        self.run_for(det, self.WINK, 0.0, 0.5)               # wink 0.5 s
        self.run_for(det, self.OPEN, 0.6, 1.0)               # open eyes -> progress lost
        _, (progress, fired) = self.run_for(det, self.WINK, 1.7, 0.5)
        self.assertFalse(fired)
        self.assertLess(progress, 0.7)

    def test_face_flicker_is_tolerated(self):
        det = WinkDetector(hold=1.0, grace=0.25)
        t = 0.0
        fired = False
        while t < 1.6 and not fired:
            ears = None if 0.4 < t < 0.55 else self.WINK     # tracker loses the face for 0.15 s
            fired = det.update(ears, t)[1]
            t += 0.05
        self.assertTrue(fired)


if __name__ == "__main__":
    unittest.main()
