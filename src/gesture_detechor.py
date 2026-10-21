"""Gesture / selection logic: coordinate mapping, smoothing, dwell confirmation.

Nothing here imports OpenCV, MediaPipe or Pygame, so it is fully unit-testable.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

Point = Tuple[float, float]
Rect = Tuple[float, float, float, float]


# ------------------------------------------------------------------ mapping
def cell_from_point(point: Optional[Point], rect: Rect, rows: int = 3, cols: int = 3,
                    deadzone: float = 0.0) -> Optional[int]:
    """Map a point to a cell index (row * 3 + col); None if outside or on an inner border."""
    if point is None:
        return None
    x, y = point
    rx, ry, rw, rh = rect
    if not (rx <= x < rx + rw and ry <= y < ry + rh):
        return None
    cw, ch = rw / cols, rh / rows
    col = min(int((x - rx) / cw), cols - 1)
    row = min(int((y - ry) / ch), rows - 1)
    if deadzone > 0:
        dx = (x - rx) - col * cw
        dy = (y - ry) - row * ch
        if (col > 0 and dx < deadzone) or (col < cols - 1 and cw - dx < deadzone):
            return None
        if (row > 0 and dy < deadzone) or (row < rows - 1 and ch - dy < deadzone):
            return None
    return row * cols + col


def cell_rect(cell: int, rect: Rect, rows: int = 3, cols: int = 3) -> Rect:
    rx, ry, rw, rh = rect
    row, col = divmod(cell, cols)
    cw, ch = rw / cols, rh / rows
    return (rx + col * cw, ry + row * ch, cw, ch)


def cell_center(cell: int, rect: Rect) -> Point:
    x, y, w, h = cell_rect(cell, rect)
    return (x + w / 2, y + h / 2)


# ---------------------------------------------------------------- smoothing
class PointSmoother:
    """Exponential moving average to reduce hand jitter."""

    def __init__(self, alpha: float = 0.45) -> None:
        self.alpha = alpha
        self._last: Optional[Point] = None

    def reset(self) -> None:
        self._last = None

    def update(self, point: Optional[Point]) -> Optional[Point]:
        if point is None:
            self._last = None
            return None
        if self._last is None:
            self._last = point
        else:
            a = self.alpha
            self._last = (a * point[0] + (1 - a) * self._last[0],
                          a * point[1] + (1 - a) * self._last[1])
        return self._last


# -------------------------------------------------------------------- dwell
class DwellSelector:
    """Confirms a target after it has been held steadily for `dwell_time` seconds.

    * short hand loss / border flicker (<= grace) does not reset the timer
    * after a confirmation the same target is LOCKED until the hand moves to another
      target or leaves, so one hold can never fire twice
    """

    def __init__(self, dwell_time: float = 1.0, grace: float = 0.3) -> None:
        self.dwell_time = dwell_time
        self.grace = grace
        self.reset()

    def reset(self) -> None:
        self.current = None
        self.locked = None
        self._start = 0.0
        self._last_seen = 0.0

    def update(self, target, now: float):
        """Returns (progress 0..1, confirmed_target or None)."""
        if target is None:
            gone = now - self._last_seen
            if gone > self.grace:
                self.current = None
                self.locked = None
                return 0.0, None
            if self.current is None:
                return 0.0, None
            frozen = (self._last_seen - self._start) / self.dwell_time
            return max(0.0, min(1.0, frozen)), None

        self._last_seen = now
        if self.locked is not None:
            if target == self.locked:
                return 0.0, None
            self.locked = None
        if target != self.current:
            self.current = target
            self._start = now
        progress = min(1.0, (now - self._start) / self.dwell_time)
        if progress >= 1.0 - 1e-9:                   # tolerance for float rounding
            progress = 1.0
            self.locked = target
            self.current = None
            return 1.0, target
        return progress, None


# -------------------------------------------------------------------- hands
def pick_active_hand(hands: Sequence, player_index: int, use_zones: bool):
    """Choose the hand that belongs to the active player.

    Without zones every visible hand may play (only one player moves at a time).
    With zones Player 1 uses hands whose wrist is on the LEFT half of the (mirrored)
    image and Player 2 the RIGHT half; the other player's hand is ignored.
    """
    candidates = list(hands)
    if use_zones:
        left = player_index == 0
        candidates = [h for h in candidates if (h.wrist[0] < 0.5) == left]
    return candidates[0] if candidates else None


PINCH_RATIO = 0.30      # thumb-tip to index-tip distance, as a fraction of hand size
PALM_RATIO = 1.10       # more tolerant: only has to tell an open hand from a fist / pointing finger
EXTENDED_RATIO = 1.2    # fingertip-to-wrist / pip-to-wrist distance when a finger is straight


def _hand_size(lm: Sequence[Point]) -> float:
    return max(math.dist(lm[0], lm[9]), 1e-6)            # wrist -> middle-finger knuckle


def _finger_ratio(lm: Sequence[Point], tip: int, pip: int) -> float:
    return math.dist(lm[0], lm[tip]) / max(math.dist(lm[0], lm[pip]), 1e-6)


def classify_gesture(lm: Sequence[Point]):
    """Which symbol is this hand showing?

    "X"  = INDEX finger + THUMB touching (OK sign / pinch)
    "O"  = INDEX finger straight, middle/ring/pinky folded, thumb NOT touching it
    None = anything else (fist, open hand, ...) -> ignored
    """
    if len(lm) < 21:
        return None
    size = _hand_size(lm)
    pinch = math.dist(lm[4], lm[8]) < PINCH_RATIO * size
    # a real pinch happens away from the palm (a fist also brings thumb + index close)
    if pinch and math.dist(lm[0], pointer_for(lm, "X")) > 1.1 * size:
        return "X"
    if (not pinch and _finger_ratio(lm, 8, 6) > EXTENDED_RATIO
            and all(_finger_ratio(lm, t, p) < EXTENDED_RATIO for t, p in ((12, 10), (16, 14), (20, 18)))):
        return "O"
    return None


def pointer_for(lm: Sequence[Point], symbol: str) -> Point:
    """Point used to aim: pinch centre for X, index fingertip for O."""
    if symbol == "X":
        return ((lm[4][0] + lm[8][0]) / 2, (lm[4][1] + lm[8][1]) / 2)
    return lm[8]


def is_open_palm(lm: Sequence[Point]) -> bool:
    """Raised open hand: 4 fingers straight, thumb out, fingers pointing up."""
    if len(lm) < 21:
        return False
    size = _hand_size(lm)
    if not all(_finger_ratio(lm, t, p) > PALM_RATIO for t, p in ((8, 6), (12, 10), (16, 14), (20, 18))):
        return False
    if math.dist(lm[4], lm[5]) < 0.20 * size:            # thumb folded across the palm
        return False
    return lm[12][1] < lm[0][1] - 0.5 * size              # middle fingertip well above the wrist


class SwipeBackDetector:
    """Raise an OPEN PALM and swipe it LEFT -> 'back'.

    Works on the mirrored image, so moving your hand to your left = x decreasing.
    update() returns (progress 0..1, triggered). A cooldown prevents double triggers.
    """

    def __init__(self, distance: float = 0.18, window: float = 0.9,
                 cooldown: float = 1.2, grace: float = 0.35) -> None:
        self.distance, self.window, self.cooldown, self.grace = distance, window, cooldown, grace
        self.reset()

    def reset(self) -> None:
        self._hist = []
        self._last_ok = -99.0
        self._cool_until = -99.0

    def update(self, lm, now: float):
        if now < self._cool_until:
            self._hist.clear()
            return 0.0, False
        if lm is None or not is_open_palm(lm):
            if now - self._last_ok > self.grace:
                self._hist.clear()
            return 0.0, False
        self._last_ok = now
        x = sum(lm[i][0] for i in (0, 5, 9, 13, 17)) / 5   # palm centre (averaged = steadier)
        y = sum(lm[i][1] for i in (0, 5, 9, 13, 17)) / 5
        self._hist.append((now, x, y))
        self._hist = [h for h in self._hist if now - h[0] <= self.window]
        _, x_max, y_at_max = max(self._hist, key=lambda h: h[1])
        dx, dy = x_max - x, abs(y - y_at_max)
        if dx <= 0:
            return 0.0, False
        progress = min(1.0, dx / self.distance)
        if progress >= 1.0 and dy <= 1.2 * dx:             # mostly horizontal
            self._cool_until = now + self.cooldown
            self._hist.clear()
            return 1.0, True
        return progress, False


def is_middle_pinch(lm: Sequence[Point]) -> bool:
    """THUMB + MIDDLE finger tips touching = 'click' (menu control).

    Rejects a closed fist (thumb and middle also meet there) by requiring the touch
    point to be away from the wrist.
    """
    if len(lm) < 21:
        return False
    size = _hand_size(lm)
    if math.dist(lm[4], lm[12]) >= PINCH_RATIO * size:
        return False
    mid = ((lm[4][0] + lm[12][0]) / 2, (lm[4][1] + lm[12][1]) / 2)
    return math.dist(lm[0], mid) > 1.0 * size


def is_start_sign(lm: Sequence[Point]) -> bool:
    """THUMB + INDEX + LITTLE finger out, middle and ring folded ('I love you' sign) = start."""
    if len(lm) < 21:
        return False
    size = _hand_size(lm)
    out = lambda t, p: _finger_ratio(lm, t, p) > EXTENDED_RATIO
    folded = lambda t, p: _finger_ratio(lm, t, p) < EXTENDED_RATIO
    return (out(8, 6) and out(20, 18) and folded(12, 10) and folded(16, 14)
            and math.dist(lm[4], lm[5]) > 0.45 * size)      # thumb stuck out, not tucked in


class HoldDetector:
    """True after a condition has been held `hold` seconds (brief drop-outs <= grace are ignored).

    update(active, now) -> (progress 0..1, fired). Fires once, then needs the condition to
    stop before it can fire again.
    """

    def __init__(self, hold: float = 0.6, grace: float = 0.2) -> None:
        self.hold, self.grace = hold, grace
        self.reset()

    def reset(self) -> None:
        self._start = None
        self._last = -99.0
        self._locked = False

    def update(self, active: bool, now: float):
        if not active:
            if now - self._last > self.grace:
                self._start = None
                self._locked = False
            return 0.0, False
        self._last = now
        if self._locked:
            return 0.0, False
        if self._start is None:
            self._start = now
        progress = min(1.0, (now - self._start) / self.hold)
        if progress >= 1.0 - 1e-9:
            self._locked = True
            self._start = None
            return 1.0, True
        return progress, False


def index_extended(landmarks: Sequence[Point]) -> bool:
    """True if the index finger points out (orientation independent).

    A closed fist is an ambiguous gesture and is ignored.
    """
    if len(landmarks) < 21:
        return False
    wrist, pip, tip = landmarks[0], landmarks[6], landmarks[8]
    return math.dist(wrist, tip) > math.dist(wrist, pip) * 1.15


# --------------------------------------------------------------------- wink
CLOSED_EAR = 0.13       # an eye below this openness counts as closed (photo test: closed 0.02, open 0.24)
OPEN_EAR = 0.17         # the other eye must be at least this open


def eye_aspect_ratio(p: Sequence[Point]) -> float:
    """Eye openness from 6 points (corner, upper, upper, corner, lower, lower).
    ~0.2-0.3 for an open eye, ~0.0-0.1 for a closed one."""
    return (math.dist(p[1], p[5]) + math.dist(p[2], p[4])) / (2 * max(math.dist(p[0], p[3]), 1e-6))


def is_wink(ears) -> bool:
    """One eye closed while the other stays open (a normal blink closes both)."""
    if ears is None:
        return False
    low, high = sorted(ears)
    return low < CLOSED_EAR and high > OPEN_EAR


class WinkDetector:
    """WINK held for `hold` seconds = fire once. Blinks and flickers never reach that long."""

    def __init__(self, hold: float = 1.2, grace: float = 0.25) -> None:
        self._hold = HoldDetector(hold, grace)

    def reset(self) -> None:
        self._hold.reset()

    def update(self, ears, now: float):
        """ears = (left, right) eye openness or None.  Returns (progress 0..1, fired)."""
        return self._hold.update(is_wink(ears), now)
