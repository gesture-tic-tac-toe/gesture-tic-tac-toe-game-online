import unittest
from types import SimpleNamespace

from src.gesture_detector import (DwellSelector, PointSmoother, cell_from_point, cell_rect,
                                  classify_gesture, index_extended, pick_active_hand, pointer_for,
                                  is_open_palm, SwipeBackDetector)

RECT = (100, 100, 300, 300)          # each cell = 100 x 100


class CellMappingTests(unittest.TestCase):                       # Cell Mapping Test
    def test_every_cell_center(self):
        for row in range(3):
            for col in range(3):
                p = (100 + col * 100 + 50, 100 + row * 100 + 50)
                self.assertEqual(cell_from_point(p, RECT), row * 3 + col)

    def test_outside_returns_none(self):
        for p in [(99, 150), (150, 99), (400, 150), (150, 400), None]:
            self.assertIsNone(cell_from_point(p, RECT))

    def test_deadzone_only_on_inner_borders(self):
        self.assertIsNone(cell_from_point((199, 150), RECT, deadzone=10))   # border 0|1
        self.assertEqual(cell_from_point((101, 101), RECT, deadzone=10), 0)  # outer edge ok
        self.assertEqual(cell_from_point((250, 250), RECT, deadzone=10), 4)

    def test_cell_rect(self):
        self.assertEqual(cell_rect(5, RECT), (300, 200, 100, 100))


class DwellTests(unittest.TestCase):                             # Dwell Test
    def test_confirms_after_dwell_time(self):
        d = DwellSelector(1.0, 0.3)
        self.assertEqual(d.update(4, 0.0), (0.0, None))
        p, c = d.update(4, 0.5)
        self.assertAlmostEqual(p, 0.5)
        self.assertIsNone(c)
        self.assertEqual(d.update(4, 1.0), (1.0, 4))

    def test_moving_to_other_cell_restarts_timer(self):
        d = DwellSelector(1.0, 0.3)
        d.update(4, 0.0)
        d.update(5, 0.9)
        self.assertIsNone(d.update(5, 1.2)[1])
        self.assertEqual(d.update(5, 1.9)[1], 5)

    def test_short_hand_loss_is_tolerated_long_loss_resets(self):
        d = DwellSelector(1.0, 0.3)
        d.update(4, 0.0)
        d.update(None, 0.2)                                       # 0.2 s loss < grace
        self.assertEqual(d.update(4, 1.0)[1], 4)
        d2 = DwellSelector(1.0, 0.3)
        d2.update(4, 0.0)
        d2.update(None, 0.5)                                      # 0.5 s loss > grace -> reset
        self.assertIsNone(d2.update(4, 1.0)[1])

    def test_no_double_fire_until_hand_moves(self):
        d = DwellSelector(1.0, 0.3)
        d.update(4, 0.0)
        self.assertEqual(d.update(4, 1.0)[1], 4)
        for t in (1.1, 2.0, 3.0):
            self.assertEqual(d.update(4, t), (0.0, None))         # locked
        d.update(5, 3.1)                                          # moved away -> unlocked
        self.assertEqual(d.update(5, 4.1)[1], 5)


class HandTests(unittest.TestCase):
    def test_smoother_reduces_jitter(self):
        s = PointSmoother(0.5)
        s.update((0, 0))
        self.assertEqual(s.update((10, 10)), (5, 5))
        self.assertIsNone(s.update(None))

    def test_zones_select_correct_hand(self):
        left = SimpleNamespace(wrist=(0.2, 0.5))
        right = SimpleNamespace(wrist=(0.8, 0.5))
        self.assertIs(pick_active_hand([left, right], 0, True), left)
        self.assertIs(pick_active_hand([left, right], 1, True), right)
        self.assertIsNone(pick_active_hand([left], 1, True))
        self.assertIs(pick_active_hand([left, right], 1, False), left)   # zones off: any hand
        self.assertIsNone(pick_active_hand([], 0, False))

    def test_index_extended_vs_fist(self):
        pts = [(0.5, 0.9)] * 21                                   # all at the wrist
        pointing = list(pts)
        pointing[6], pointing[8] = (0.5, 0.6), (0.5, 0.3)         # tip far beyond pip
        fist = list(pts)
        fist[6], fist[8] = (0.5, 0.6), (0.5, 0.62)                # tip folded back
        self.assertTrue(index_extended(pointing))
        self.assertFalse(index_extended(fist))
        self.assertFalse(index_extended(pts[:5]))


def lm(**over):
    """Synthetic hand: wrist (0.5, 0.9), middle knuckle (0.5, 0.6) -> hand size 0.3."""
    pts = [(0.5, 0.9)] * 21
    pts[9] = (0.5, 0.6)
    for k, v in over.items():
        pts[int(k[1:])] = v
    return pts


class SymbolGestureTests(unittest.TestCase):
    def test_o_is_index_finger_only(self):                    # photo 2
        hand = lm(p6=(0.5, 0.55), p8=(0.5, 0.2), p10=(0.5, 0.65), p12=(0.5, 0.7))
        self.assertEqual(classify_gesture(hand), "O")
        self.assertEqual(pointer_for(hand, "O"), (0.5, 0.2))

    def test_x_is_index_and_thumb_touching(self):             # photo 1 (OK sign)
        hand = lm(p6=(0.5, 0.6), p8=(0.55, 0.35), p4=(0.56, 0.36),
                  p10=(0.5, 0.5), p12=(0.5, 0.15), p14=(0.45, 0.5), p16=(0.45, 0.15))
        self.assertEqual(classify_gesture(hand), "X")
        px, py = pointer_for(hand, "X")
        self.assertAlmostEqual(px, 0.555)
        self.assertAlmostEqual(py, 0.355)

    def test_fist_open_hand_and_garbage_are_ignored(self):
        fist = lm(p6=(0.5, 0.65), p8=(0.5, 0.7), p4=(0.51, 0.72))
        open_hand = lm(p6=(0.5, 0.55), p8=(0.5, 0.2), p10=(0.5, 0.5), p12=(0.5, 0.15),
                       p14=(0.45, 0.5), p16=(0.45, 0.15), p18=(0.4, 0.5), p20=(0.4, 0.2))
        self.assertIsNone(classify_gesture(fist))
        self.assertIsNone(classify_gesture(open_hand))
        self.assertIsNone(classify_gesture(lm()[:5]))


def palm(dx=0.0):
    """Raised open hand (fingers up, thumb out). dx shifts it sideways."""
    pts = [(0.5 + dx, 0.9)] * 21
    pts[9] = (0.5 + dx, 0.6)
    for pip, tip, x in ((6, 8, 0.56), (10, 12, 0.5), (14, 16, 0.44), (18, 20, 0.38)):
        pts[pip], pts[tip] = (x + dx, 0.55), (x + dx, 0.2)
    pts[5], pts[4] = (0.56 + dx, 0.62), (0.80 + dx, 0.65)
    return pts


class BackSwipeTests(unittest.TestCase):
    def test_open_palm_detected_but_pointing_and_fist_are_not(self):
        self.assertTrue(is_open_palm(palm()))
        o_hand = lm(p6=(0.5, 0.55), p8=(0.5, 0.2), p10=(0.5, 0.65), p12=(0.5, 0.7))
        fist = lm(p6=(0.5, 0.65), p8=(0.5, 0.7), p4=(0.51, 0.72))
        self.assertFalse(is_open_palm(o_hand))
        self.assertFalse(is_open_palm(fist))

    def test_fast_left_swipe_triggers_back(self):
        d = SwipeBackDetector()
        fired = False
        for i in range(12):                                   # 0.7 -> 0.4 over ~0.4 s
            _, f = d.update(palm(0.2 - i * 0.03), i * 0.04)
            fired = fired or f
        self.assertTrue(fired)

    def test_right_swipe_slow_drift_and_non_palm_do_not_trigger(self):
        d = SwipeBackDetector()
        self.assertFalse(any(d.update(palm(-0.2 + i * 0.03), i * 0.04)[1] for i in range(12)))   # to the right
        d = SwipeBackDetector()
        self.assertFalse(any(d.update(palm(0.2 - i * 0.002), i * 0.04)[1] for i in range(75)))   # slow drift
        d = SwipeBackDetector()
        o_hand = lm(p6=(0.5, 0.55), p8=(0.5, 0.2), p10=(0.5, 0.65), p12=(0.5, 0.7))
        self.assertFalse(any(d.update(o_hand, i * 0.04)[1] for i in range(12)))

    def test_cooldown_prevents_double_trigger(self):
        d = SwipeBackDetector()
        hits = sum(d.update(palm(0.3 - i * 0.03), i * 0.04)[1] for i in range(20))
        self.assertEqual(hits, 1)


def start_hand():
    """Thumb out, index + little finger up, middle + ring folded."""
    pts = [(0.5, 0.9)] * 21
    pts[9] = (0.5, 0.6)
    pts[5], pts[4] = (0.56, 0.62), (0.80, 0.65)
    pts[6], pts[8] = (0.56, 0.55), (0.56, 0.2)
    pts[10], pts[12] = (0.5, 0.65), (0.5, 0.7)
    pts[14], pts[16] = (0.44, 0.65), (0.44, 0.7)
    pts[18], pts[20] = (0.38, 0.55), (0.38, 0.2)
    return pts


class MenuGestureTests(unittest.TestCase):
    def test_start_sign(self):
        from src.gesture_detector import is_start_sign
        self.assertTrue(is_start_sign(start_hand()))
        self.assertFalse(is_start_sign(palm()))                       # open hand
        self.assertFalse(is_start_sign(lm(p6=(0.5, 0.55), p8=(0.5, 0.2),
                                          p10=(0.5, 0.65), p12=(0.5, 0.7))))   # index only

    def test_middle_pinch(self):
        from src.gesture_detector import is_middle_pinch
        hand = lm(p4=(0.55, 0.3), p12=(0.56, 0.31), p8=(0.5, 0.15))
        self.assertTrue(is_middle_pinch(hand))
        self.assertFalse(is_middle_pinch(palm()))
        self.assertFalse(is_middle_pinch(lm(p4=(0.51, 0.72), p12=(0.5, 0.7))))   # fist near wrist

    def test_hold_detector_fires_once(self):
        from src.gesture_detector import HoldDetector
        h = HoldDetector(0.5)
        fired = [h.update(True, i * 0.05)[1] for i in range(30)]
        self.assertEqual(sum(fired), 1)
        h.update(False, 2.0)
        self.assertTrue(any(h.update(True, 2.1 + i * 0.05)[1] for i in range(15)))
        h2 = HoldDetector(0.5)
        self.assertFalse(any(h2.update(i % 10 < 3, i * 0.05)[1] for i in range(40)))   # flickering


if __name__ == "__main__":
    unittest.main()
