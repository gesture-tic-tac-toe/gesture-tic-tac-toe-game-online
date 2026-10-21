"""Renderer: everything that is drawn with Pygame (no game rules in here)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence

import cv2
import numpy as np
import pygame

from .config import Config, FONT_DIR, ROOT, X, O, tr
from .game_state import Game, State
from .game_rules import WIN
from .gesture_detector import cell_rect, cell_center
from .hand_tracker import HAND_CONNECTIONS

WINK_IMAGE = ROOT / "assets" / "images" / "wink_exit.png"

COLORS = {
    "bg": (18, 20, 28), "panel": (28, 32, 46), "text": (242, 242, 248),
    "muted": (165, 170, 188), "x": (255, 99, 99), "o": (90, 190, 255),
    "good": (80, 220, 130), "bad": (255, 85, 85), "accent": (255, 205, 70),
    "line": (225, 228, 240), "btn": (46, 52, 76), "btn_hover": (70, 82, 128),
}


THEMES = {
    "midnight": dict(bg=(18, 20, 28), panel=(28, 32, 46), x=(255, 99, 99), o=(90, 190, 255),
                     accent=(255, 205, 70), btn=(46, 52, 76), btn_hover=(70, 82, 128),
                     good=(80, 220, 130), line=(225, 228, 240)),
    "neon": dict(bg=(10, 6, 24), panel=(24, 12, 48), x=(255, 60, 172), o=(0, 240, 255),
                 accent=(190, 255, 60), btn=(40, 20, 80), btn_hover=(80, 40, 150),
                 good=(60, 255, 150), line=(200, 170, 255)),
    "ocean": dict(bg=(6, 24, 34), panel=(10, 42, 58), x=(255, 138, 101), o=(128, 222, 234),
                  accent=(255, 236, 153), btn=(16, 66, 88), btn_hover=(24, 104, 134),
                  good=(105, 240, 174), line=(214, 240, 250)),
    "sunset": dict(bg=(34, 14, 24), panel=(58, 24, 40), x=(255, 183, 77), o=(186, 104, 200),
                   accent=(255, 241, 118), btn=(88, 36, 60), btn_hover=(138, 56, 88),
                   good=(129, 236, 140), line=(255, 224, 230)),
}
THEME_NAMES = tuple(THEMES)


def make_icon(size: int = 64) -> pygame.Surface:
    """Window icon drawn in code (no image file needed)."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(s, (28, 32, 46), s.get_rect(), border_radius=size // 5)
    for i in (1, 2):
        pygame.draw.line(s, (225, 228, 240), (size * i / 3, 6), (size * i / 3, size - 6), 3)
        pygame.draw.line(s, (225, 228, 240), (6, size * i / 3), (size - 6, size * i / 3), 3)
    m = size / 6
    pygame.draw.line(s, THEMES["midnight"]["x"], (m - 7, m - 7), (m + 7, m + 7), 4)
    pygame.draw.line(s, THEMES["midnight"]["x"], (m - 7, m + 7), (m + 7, m - 7), 4)
    pygame.draw.circle(s, THEMES["midnight"]["o"], (int(size / 2), int(size / 2)), int(size / 8), 4)
    pygame.draw.circle(s, THEMES["midnight"]["o"], (int(size - m), int(size - m)), int(size / 8), 4)
    return s


@dataclass
class Button:
    id: str
    label: str
    rect: pygame.Rect
    tint: Optional[str] = None        # key of COLORS used for the border (e.g. difficulty colours)


class Renderer:
    def __init__(self, screen: pygame.Surface, cfg: Config) -> None:
        self.screen = screen
        self.cfg = cfg
        self.W, self.H = screen.get_size()
        self._bg: Optional[pygame.Surface] = None
        self._dim = pygame.Surface((self.W, self.H))
        self._dim.fill((8, 10, 18))
        self._dim.set_alpha(150)
        self.particles: list = []
        rnd = random.Random(7)
        self._floaters = [dict(x=rnd.random(), y=rnd.random(), sym=X if i % 2 else O,
                               size=rnd.randint(60, 130), speed=rnd.uniform(0.01, 0.03),
                               phase=rnd.uniform(0, 6.28)) for i in range(11)]
        self.set_theme(cfg.theme)
        self.reload_fonts()
        self._wink_img = None
        try:                                               # reference photo shown in the instructions
            img = pygame.image.load(str(WINK_IMAGE)).convert()
            self._wink_img = pygame.transform.smoothscale(img, (170, int(170 * img.get_height() / img.get_width())))
        except (pygame.error, OSError, FileNotFoundError):
            pass

    def set_theme(self, name: str) -> None:
        name = name if name in THEMES else "midnight"
        COLORS.update(THEMES[name])
        self._dim.fill(tuple(int(c * 0.45) for c in COLORS["bg"]))

    # ------------------------------------------------------------- fonts
    def _khmer_font_path(self) -> Optional[str]:
        files = sorted(list(FONT_DIR.glob("*.ttf")) + list(FONT_DIR.glob("*.otf")))
        khmer = [f for f in files if "khmer" in f.name.lower()]
        pick = khmer or files
        return str(pick[0]) if pick else None

    def has_khmer_font(self) -> bool:
        return self._khmer_font_path() is not None

    def reload_fonts(self) -> None:
        self._fonts = {}
        self._font_path = self._khmer_font_path() if self.cfg.language == "km" else None

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            if self._font_path:
                f = pygame.font.Font(self._font_path, size)
            else:
                f = pygame.font.SysFont("segoeui,arial,helvetica,dejavusans,freesans", size, bold=bold)
            self._fonts[key] = f
        return self._fonts[key]

    # ------------------------------------------------------------ helpers
    def player_color(self, index: int):
        return COLORS["x"] if index == 0 else COLORS["o"]

    def text(self, s: str, size: int, color, pos, anchor: str = "topleft",
             bold: bool = False, shadow: bool = True) -> pygame.Rect:
        f = self.font(size, bold)
        surf = f.render(s, True, color)
        rect = surf.get_rect(**{anchor: pos})
        if shadow:
            self.screen.blit(f.render(s, True, (0, 0, 0)), rect.move(2, 2))
        self.screen.blit(surf, rect)
        return rect

    def font_q(self, size: int, bold: bool = False) -> pygame.font.Font:
        """Font with the size rounded to a multiple of 6 (keeps the font cache small when animating)."""
        return self.font(max(6, int(round(size / 6)) * 6), bold)

    def box(self, rect, color, alpha: int = 200, radius: int = 18, border=None, border_w: int = 2) -> None:
        rect = pygame.Rect(rect)
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
        self.screen.blit(s, rect.topleft)
        if border:
            pygame.draw.rect(self.screen, border, rect, border_w, border_radius=radius)

    def ring(self, center, radius: int, progress: float, color, width: int = 8) -> None:
        pygame.draw.circle(self.screen, (255, 255, 255), center, radius, 2)
        if progress <= 0:
            return
        steps = max(2, int(64 * min(progress, 1.0)))
        pts = [(center[0] + radius * math.cos(-math.pi / 2 + 2 * math.pi * progress * i / steps),
                center[1] + radius * math.sin(-math.pi / 2 + 2 * math.pi * progress * i / steps))
               for i in range(steps + 1)]
        pygame.draw.lines(self.screen, color, False, pts, width)

    # --------------------------------------------------------- background
    def set_frame(self, frame_bgr: Optional[np.ndarray]) -> None:
        if frame_bgr is None:
            self._bg = None
            return
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        surf = pygame.surfarray.make_surface(np.swapaxes(rgb, 0, 1))
        self._bg = pygame.transform.scale(surf, (self.W, self.H))

    def draw_background(self) -> None:
        if self._bg is not None:
            self.screen.blit(self._bg, (0, 0))
            self.screen.blit(self._dim, (0, 0))
        else:
            self.screen.fill(COLORS["bg"])

    def draw_face_mesh(self, landmarks) -> None:
        if len(landmarks) < 468:
            return
        paths = (
            (10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365,
             379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93,
             234, 127, 162, 21, 54, 103, 67, 109),
            (33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246),
            (362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398),
            (61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267,
             0, 37, 39, 40, 185),
            (78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317,
             14, 87, 178, 88, 95),
        )
        colors = (COLORS["good"], COLORS["accent"], COLORS["accent"],
                  COLORS["x"], COLORS["x"])
        for path, color in zip(paths, colors):
            points = [(int(landmarks[i][0] * self.W), int(landmarks[i][1] * self.H))
                      for i in path]
            pygame.draw.lines(self.screen, color, True, points, 1 if color == COLORS["good"] else 2)

    def draw_floaters(self, now: float) -> None:
        """Soft drifting X / O shapes behind the menu screens."""
        for f in self._floaters:
            y = (f["y"] - now * f["speed"]) % 1.2 - 0.1
            x = f["x"] + 0.02 * math.sin(now * 0.6 + f["phase"])
            size = f["size"]
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            self._symbol(f["sym"], (0, 0, size, size), 1.0, surf)
            surf.set_alpha(38)
            self.screen.blit(surf, (int(x * self.W - size / 2), int(y * self.H - size / 2)))

    # ---------------------------------------------------------- symbols
    def _symbol(self, sym: str, rect, scale: float, surf=None) -> None:
        surf = surf if surf is not None else self.screen
        cx, cy = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
        half = rect[2] * 0.28 * scale
        width = max(2, int(rect[2] * 0.09 * scale))
        if scale <= 0.02:
            return
        if sym == X:
            c = COLORS["x"]
            for a, b in (((-1, -1), (1, 1)), ((-1, 1), (1, -1))):
                p1 = (cx + a[0] * half, cy + a[1] * half)
                p2 = (cx + b[0] * half, cy + b[1] * half)
                pygame.draw.line(surf, c, p1, p2, width)
                pygame.draw.circle(surf, c, p1, width // 2)
                pygame.draw.circle(surf, c, p2, width // 2)
        else:
            pygame.draw.circle(surf, COLORS["o"], (int(cx), int(cy)),
                               max(3, int(half * 1.15)), width)

    # ------------------------------------------------------------- board
    def draw_board(self, game: Game, target: Optional[int], progress: float, now: float,
                   hover_symbol: Optional[str] = None, hover_ok: bool = True) -> None:
        rect = self.cfg.board_rect
        bx, by, bw, bh = rect
        self.box((bx - 16, by - 16, bw + 32, bh + 32), COLORS["panel"], 175, 26)

        playing = game.state is State.PLAYING
        active_color = self.player_color(game.turns.current_index)

        if playing and target is not None:
            r = cell_rect(target, rect)
            occupied = not game.board.is_empty(target)
            col = COLORS["bad"] if (occupied or not hover_ok) else active_color
            hl = pygame.Surface((int(r[2]) - 4, int(r[3]) - 4), pygame.SRCALPHA)
            hl.fill((*col, 80))
            self.screen.blit(hl, (r[0] + 2, r[1] + 2))
            if hover_symbol and not occupied:                 # ghost preview of the symbol
                ghost = pygame.Surface((int(r[2]), int(r[3])), pygame.SRCALPHA)
                self._symbol(hover_symbol, (0, 0, r[2], r[3]), 1.0, ghost)
                ghost.set_alpha(120 if hover_ok else 70)
                self.screen.blit(ghost, (r[0], r[1]))

        hint = getattr(game, "hint_cell", None)
        if playing and hint is not None and now < game.hint_until:
            r = cell_rect(hint, rect)
            pulse = 0.5 + 0.5 * math.sin(now * 8)
            pygame.draw.rect(self.screen, COLORS["accent"], (r[0] + 6, r[1] + 6, r[2] - 12, r[3] - 12),
                             3 + int(3 * pulse), border_radius=14)

        for i in (1, 2):                                   # grid lines
            pygame.draw.line(self.screen, COLORS["line"], (bx + bw * i / 3, by + 6),
                             (bx + bw * i / 3, by + bh - 6), 5)
            pygame.draw.line(self.screen, COLORS["line"], (bx + 6, by + bh * i / 3),
                             (bx + bw - 6, by + bh * i / 3), 5)

        for cell, sym in enumerate(game.board.flat()):     # symbols with pop-in animation
            if sym:
                t = min(1.0, (now - game.placed_at.get(cell, -9)) / 0.25)
                self._symbol(sym, cell_rect(cell, rect), 1 - (1 - t) ** 3)

        if playing and target is not None and progress > 0:
            cx, cy = cell_center(target, rect)
            self.ring((int(cx), int(cy)), int(bw / 6 * 0.78), progress, COLORS["accent"], 9)

        out = game.outcome
        if game.state is State.ROUND_RESULT and out is not None and out.status == WIN and out.line:
            pulse = 0.5 + 0.5 * math.sin((now - game.result_at) * 6)
            for cell in out.line:
                r = cell_rect(cell, rect)
                hl = pygame.Surface((int(r[2]) - 4, int(r[3]) - 4), pygame.SRCALPHA)
                hl.fill((*COLORS["good"], int(60 + 90 * pulse)))
                self.screen.blit(hl, (r[0] + 2, r[1] + 2))
            grow = min(1.0, (now - game.result_at) / 0.5)
            a = cell_center(out.line[0], rect)
            b = cell_center(out.line[2], rect)
            end = (a[0] + (b[0] - a[0]) * grow, a[1] + (b[1] - a[1]) * grow)
            pygame.draw.line(self.screen, COLORS["good"], a, end, 14)
            pygame.draw.circle(self.screen, COLORS["good"], (int(a[0]), int(a[1])), 7)

    def draw_zones(self) -> None:
        """Divider showing the Player 1 (left) / Player 2 (right) camera zones."""
        mid = self.W // 2
        for y in range(0, self.H, 24):
            pygame.draw.line(self.screen, COLORS["muted"], (mid, y), (mid, y + 10), 2)
        self.text("P1", 22, COLORS["x"], (20, 12))
        self.text("P2", 22, COLORS["o"], (self.W - 20, 12), "topright")

    # ------------------------------------------------------------- panel
    def draw_side_panel(self, game: Game, now: float, status: str, timer_left: Optional[float] = None) -> None:
        lang = self.cfg.language
        x0, y0, w = 700, 60, 530
        self.box((x0, y0, w, 580), COLORS["panel"], 175, 26)
        self.text(tr(lang, "title"), 38, COLORS["text"], (x0 + w // 2, y0 + 40), "center", True)

        for i in (0, 1):                                   # player cards
            p = game.players[i]
            card = pygame.Rect(x0 + 20 + i * 250, y0 + 85, 240, 130)
            active = game.state is State.PLAYING and game.turns.current_index == i
            self.box(card, COLORS["btn"], 230, 16,
                     COLORS["accent"] if active else None, 4)
            self.text(p.symbol, 52, self.player_color(i), (card.x + 18, card.y + 12), "topleft", True)
            self.text(str(game.scores.wins[i]), 60, COLORS["text"], (card.right - 20, card.y + 8),
                      "topright", True)
            self.text(p.name, 26, COLORS["text"], (card.x + 18, card.bottom - 56))
            target = self.cfg.match_target
            for k in range(min(target, 7)):                     # match progress dots
                filled = k < game.scores.wins[i]
                c = (card.x + 24 + k * 18, card.bottom - 16)
                pygame.draw.circle(self.screen, self.player_color(i) if filled else (110, 116, 140), c,
                                   6 if filled else 5, 0 if filled else 2)
            if i == 1 and self.cfg.mode == "ai":
                self.text(tr(lang, self.cfg.ai_level).split(" (")[0], 18, COLORS["muted"],
                          (card.right - 14, card.bottom - 14), "bottomright", shadow=False)

        playing_now = game.state in (State.PLAYING, State.PAUSED)
        info = f"{tr(lang, 'round', n=game.scores.rounds_played + (1 if playing_now else 0))}" \
               f"   |   {tr(lang, 'draws')}: {game.scores.draws}"
        if self.cfg.match_target > 0:
            info += f"   |   {tr(lang, 'target_first', n=self.cfg.match_target)}"
        self.text(info, 24, COLORS["muted"], (x0 + w // 2, y0 + 245), "center")

        if game.state is State.PLAYING:
            cur = game.turns.current
            self.text(tr(lang, "turn", name=cur.name, symbol=cur.symbol), 34,
                      self.player_color(game.turns.current_index), (x0 + w // 2, y0 + 310), "center", True)
            if status:
                self.text(status, 24, COLORS["accent"], (x0 + w // 2, y0 + 360), "center")
            if timer_left is not None:
                self.draw_turn_timer(timer_left, self.cfg.turn_timer, (x0 + 40, y0 + 398, w - 80, 14))
            if self.cfg.symbol_gestures:                      # gesture cheat-sheet
                for k, sym in enumerate((X, O)):
                    self.text(f"{sym}  =  {tr(lang, 'gesture_' + sym)}", 24,
                              self.player_color(k), (x0 + 40, y0 + 440 + k * 44))
        elif game.state is State.ROUND_RESULT:
            good = game.outcome is not None and game.outcome.status == WIN
            color = COLORS["good"] if good else COLORS["accent"]
            if game.match_winner is not None:
                bob = 4 * math.sin(now * 3)
                self.draw_crown((x0 + w // 2, int(y0 + 298 + bob)))
                self.text(game.result_text(), 36, COLORS["accent"], (x0 + w // 2, y0 + 348), "center", True)
            else:
                self.text(game.result_text(), 42, color, (x0 + w // 2, y0 + 320), "center", True)

    # ----------------------------------------------------------- buttons
    def draw_buttons(self, buttons: Sequence[Button], hover: Optional[int], progress: float) -> None:
        for i, b in enumerate(buttons):
            is_h = hover == i
            tint = COLORS[b.tint] if b.tint else None
            grow = b.rect.inflate(8, 4) if is_h else b.rect            # hovered buttons grow a little
            self.box(grow, COLORS["btn_hover"] if is_h else COLORS["btn"], 235, 14,
                     COLORS["good"] if is_h else (tint or (90, 98, 130)),
                     3 if is_h or tint else 2)
            if is_h and progress > 0:
                fill = pygame.Rect(b.rect.x + 4, b.rect.bottom - 12, int((b.rect.w - 8) * progress), 8)
                pygame.draw.rect(self.screen, COLORS["accent"], fill, border_radius=4)
            self.text(b.label, 28, COLORS["good"] if is_h else COLORS["text"],
                      b.rect.center, "center", shadow=False)

    # ----------------------------------------------------------- screens
    def draw_menu(self, buttons, hover, progress, now: float = 0.0) -> None:
        lang = self.cfg.language
        self.draw_floaters(now)
        bob = 5 * math.sin(now * 2.0)
        self.text(tr(lang, "title"), 68, COLORS["text"], (self.W // 2, 95 + bob), "center", True)
        self.text(tr(lang, "subtitle"), 26, COLORS["muted"], (self.W // 2, 155), "center")
        self.draw_buttons(buttons, hover, progress)

    def draw_difficulty(self, buttons, hover, progress, now: float = 0.0) -> None:
        self.draw_floaters(now)
        self.text(tr(self.cfg.language, "difficulty"), 58, COLORS["text"], (self.W // 2, 130), "center", True)
        self.draw_buttons(buttons, hover, progress)

    def draw_pause(self, buttons, hover, progress) -> None:
        self.screen.blit(self._dim, (0, 0))
        self.box((self.W // 2 - 270, 90, 540, 405), COLORS["panel"], 235, 26, COLORS["accent"], 3)
        self.text(tr(self.cfg.language, "paused"), 64, COLORS["accent"], (self.W // 2, 160), "center", True)
        self.draw_buttons(buttons, hover, progress)

    def draw_stats(self, stats, game, buttons, hover, progress, now: float = 0.0) -> None:
        lang = self.cfg.language
        d = stats.data
        self.draw_floaters(now)
        self.box((170, 40, self.W - 340, 535), COLORS["panel"], 215, 24)
        self.text(tr(lang, "stats_title"), 46, COLORS["accent"], (self.W // 2, 85), "center", True)
        xl, xr = 220, self.W - 220

        def row(label, value, y, color=COLORS["text"]):
            self.text(label, 26, COLORS["muted"], (xl, y), "midleft", shadow=False)
            self.text(str(value), 28, color, (xr, y), "midright", True, shadow=False)

        def heading(label, y):
            self.text(label, 28, COLORS["accent"], (xl, y), "midleft", True, shadow=False)
            pygame.draw.line(self.screen, COLORS["muted"], (xl, y + 18), (xr, y + 18), 1)

        row(tr(lang, "st_rounds"), d["rounds"], 140)
        row(tr(lang, "st_streak"), d["streak"], 176)
        row(tr(lang, "st_best"), d["best_streak"], 212)
        row(tr(lang, "st_matches"), f"{d['matches_won']} / {d['matches_lost']}", 248)
        heading(tr(lang, "st_ai"), 300)
        for k, lvl in enumerate(("easy", "medium", "hard")):
            r = d["ai"][lvl]
            row(tr(lang, lvl).split(" (")[0], f"{r['w']} / {r['l']} / {r['d']}", 345 + k * 36,
                COLORS[{"easy": "good", "medium": "accent", "hard": "bad"}[lvl]])
        heading(tr(lang, "st_pvp"), 466)
        p = d["pvp"]
        self.text(tr(lang, "st_pvp_row", p1=game.cfg.player_names[0], a=p["p1"],
                     p2=game.cfg.player_names[1], b=p["p2"], d=p["d"]), 26, COLORS["text"],
                  (self.W // 2, 515), "center", shadow=False)
        self.draw_buttons(buttons, hover, progress)

    def draw_splash(self, message: str, now: float) -> None:
        self.screen.fill(COLORS["bg"])
        self.draw_floaters(now)
        self.text(tr(self.cfg.language, "title"), 72, COLORS["text"], (self.W // 2, self.H // 2 - 90), "center", True)
        self.ring((self.W // 2, self.H // 2 + 40), 34, (now * 0.8) % 1.0, COLORS["accent"], 7)
        self.text(message, 26, COLORS["muted"], (self.W // 2, self.H // 2 + 120), "center")
        pygame.display.flip()

    def draw_instructions(self, buttons, hover, progress) -> None:
        lang = self.cfg.language
        self.box((120, 30, self.W - 240, 545), COLORS["panel"], 215, 24)
        self.text(tr(lang, "inst_title"), 46, COLORS["accent"], (self.W // 2, 75), "center", True)
        for i, line in enumerate(tr(lang, "inst")):
            self.text(line, 23, COLORS["text"], (160, 120 + i * 34))
        if self._wink_img is not None:                     # the wink = exit reference picture
            r = self._wink_img.get_rect(topright=(self.W - 140, 392))
            self.screen.blit(self._wink_img, r)
            pygame.draw.rect(self.screen, COLORS["accent"], r.inflate(6, 6), 3, border_radius=6)
            self.text(tr(lang, "wink_photo"), 20, COLORS["accent"], (r.centerx, r.bottom + 6), "midtop", True)
        self.draw_buttons(buttons, hover, progress)

    def draw_settings(self, buttons, hover, progress) -> None:
        self.text(tr(self.cfg.language, "settings"), 46, COLORS["text"], (self.W // 2, 60), "center", True)
        self.draw_buttons(buttons, hover, progress)

    def draw_setup(self, progress: float) -> None:
        lang = self.cfg.language
        c = (self.W // 2, self.H // 2)
        self.text(tr(lang, "show_hand"), 40, COLORS["text"], (c[0], c[1] - 150), "center", True)
        self.ring(c, 90, progress, COLORS["accent"], 12)

    def draw_error(self, message: str) -> None:
        self.screen.fill(COLORS["bg"])
        self.text("Gesture Tic-Tac-Toe", 54, COLORS["text"], (self.W // 2, 150), "center", True)
        for i, line in enumerate(message.split("\n")):
            self.text(line, 28, COLORS["bad"] if i == 0 else COLORS["muted"],
                      (self.W // 2, 260 + i * 44), "center")
        self.text("R = retry     ESC = exit", 26, COLORS["accent"], (self.W // 2, 500), "center")
        pygame.display.flip()

    # ------------------------------------------------------- overlays
    def draw_message(self, message: str) -> None:
        bx, by, bw, bh = self.cfg.board_rect
        rect = pygame.Rect(0, 0, 440, 52)
        rect.center = (int(bx + bw / 2), int(by + bh + 52))
        self.box(rect, COLORS["bad"], 225, 14)
        self.text(message, 26, COLORS["text"], rect.center, "center", True, shadow=False)

    def draw_banner(self, message: str) -> None:
        rect = pygame.Rect(0, 0, 520, 50)
        rect.midtop = (self.W // 2, 10)
        self.box(rect, COLORS["bad"], 230, 12)
        self.text(message, 26, COLORS["text"], rect.center, "center", True, shadow=False)

    def draw_countdown(self, label: str, frac: float) -> None:
        """Big 3 - 2 - 1 - GO! over the board; each label shrinks and fades."""
        if not label:
            return
        bx, by, bw, bh = self.cfg.board_rect
        c = (int(bx + bw / 2), int(by + bh / 2))
        go = not label.isdigit()
        size = int((150 if not go else 130) - 55 * frac)
        surf = self.font_q(size, True).render(label, True, COLORS["good"] if go else COLORS["accent"])
        surf.set_alpha(int(255 * (1 - frac ** 3)))
        self.screen.blit(surf, surf.get_rect(center=c))

    def draw_turn_timer(self, left: float, limit: int, rect) -> None:
        x, y, w, h = rect
        frac = max(0.0, min(1.0, left / max(limit, 1)))
        pygame.draw.rect(self.screen, (60, 66, 90), rect, border_radius=7)
        color = COLORS["bad"] if left <= 3 else COLORS["accent"]
        pygame.draw.rect(self.screen, color, (x, y, int(w * frac), h), border_radius=7)
        self.text(f"{left:0.0f}s", 18, COLORS["text"], (x + w + 6, y + h // 2), "midleft", shadow=False)

    def draw_crown(self, center, scale: float = 1.0) -> None:
        cx, cy = center
        pts = [(-45, 28), (-45, -12), (-22, 8), (0, -30), (22, 8), (45, -12), (45, 28)]
        poly = [(cx + px * scale, cy + py * scale) for px, py in pts]
        pygame.draw.polygon(self.screen, COLORS["accent"], poly)
        pygame.draw.polygon(self.screen, (255, 255, 255), poly, 2)
        for px, py in ((-45, -12), (0, -30), (45, -12)):
            pygame.draw.circle(self.screen, COLORS["x"], (int(cx + px * scale), int(cy + py * scale)), 6)

    def burst_confetti(self, n: int = 140) -> None:
        cols = [COLORS[k] for k in ("x", "o", "accent", "good")]
        for _ in range(n):
            self.particles.append(dict(x=random.uniform(0, self.W), y=random.uniform(-self.H * 0.7, -10),
                                       vx=random.uniform(-60, 60), vy=random.uniform(140, 340),
                                       rot=random.uniform(0, 6.28), vr=random.uniform(-7, 7),
                                       w=random.randint(8, 14), h=random.randint(4, 8),
                                       c=random.choice(cols)))

    def draw_confetti(self, dt: float) -> None:
        alive = []
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["rot"] += p["vr"] * dt
            p["vx"] += math.sin(p["rot"]) * 40 * dt
            if p["y"] > self.H + 20:
                continue
            alive.append(p)
            if p["y"] < -20:
                continue
            ca, sa = math.cos(p["rot"]), math.sin(p["rot"])
            pts = [(p["x"] + dx * ca - dy * sa, p["y"] + dx * sa + dy * ca)
                   for dx, dy in ((-p["w"] / 2, -p["h"] / 2), (p["w"] / 2, -p["h"] / 2),
                                  (p["w"] / 2, p["h"] / 2), (-p["w"] / 2, p["h"] / 2))]
            pygame.draw.polygon(self.screen, p["c"], pts)
        self.particles = alive

    def draw_cursor(self, pos, color, progress: float = 0.0) -> None:
        if pos is None:
            return
        cx, cy = int(pos[0]), int(pos[1])
        p = (cx, cy)
        points = [(cx + dx, cy + dy) for dx, dy in (
            (0, -20), (5, -6), (19, 0), (6, 5),
            (0, 20), (-6, 5), (-19, 0), (-5, -6),
        )]
        pygame.draw.polygon(self.screen, (28, 32, 46), points)
        inner = [(cx + dx, cy + dy) for dx, dy in (
            (0, -17), (3, -5), (16, 0), (5, 3),
            (0, 17), (-3, 5), (-16, 0), (-5, -3),
        )]
        pygame.draw.polygon(self.screen, (255, 133, 45), inner)
        pygame.draw.circle(self.screen, (28, 32, 46), p, 5)
        pygame.draw.circle(self.screen, color, p, 2)
        if progress > 0:
            self.ring(p, 27, progress, COLORS["accent"], 5)

    def draw_hands(self, hands, active) -> None:
        for h in hands:
            color = COLORS["accent"] if h is active else COLORS["muted"]
            pts = [(int(x * self.W), int(y * self.H)) for x, y in h.landmarks]
            for a, b in HAND_CONNECTIONS:
                pygame.draw.line(self.screen, color, pts[a], pts[b], 2)
            for p in pts:
                pygame.draw.circle(self.screen, COLORS["good"], p, 4)

    def draw_fps(self, fps: float) -> None:
        self.text(f"{fps:4.1f} FPS", 20, COLORS["muted"], (14, self.H - 36), "bottomleft")

    def draw_footer_left(self, text: str) -> None:
        self.text(text, 20, COLORS["muted"], (14, self.H - 12), "bottomleft")

    def draw_footer(self, text: str) -> None:
        self.text(text, 20, COLORS["muted"], (self.W - 20, self.H - 12), "bottomright")

    def draw_start_progress(self, progress: float, label: str) -> None:
        """Bar that fills while the start sign (thumb + index + little finger) is held."""
        if progress < 0.05:
            return
        rect = pygame.Rect(0, 0, 420, 40)
        rect.midtop = (self.W // 2, 14)
        self.box(rect, COLORS["panel"], 235, 12, COLORS["good"], 2)
        fill = pygame.Rect(rect.x + 4, rect.y + 4, int((rect.w - 8) * progress), rect.h - 8)
        pygame.draw.rect(self.screen, COLORS["good"], fill, border_radius=8)
        self.text(label + "  >>", 24, COLORS["text"], rect.center, "center", True)

    def draw_exit_progress(self, progress: float, label: str) -> None:
        """Red bar that fills while a WINK is held (the game quits when it is full)."""
        if progress < 0.05:
            return
        rect = pygame.Rect(0, 0, 420, 40)
        rect.midtop = (self.W // 2, 62)
        self.box(rect, COLORS["panel"], 235, 12, COLORS["bad"], 2)
        fill = pygame.Rect(rect.x + 4, rect.y + 4, int((rect.w - 8) * progress), rect.h - 8)
        pygame.draw.rect(self.screen, COLORS["bad"], fill, border_radius=8)
        self.text(";)  " + label, 24, COLORS["text"], rect.center, "center", True)

    def draw_back_progress(self, progress: float, label: str) -> None:
        """Bar that fills while an open palm is swiped to the left."""
        if progress < 0.05:
            return
        rect = pygame.Rect(0, 0, 420, 40)
        rect.midtop = (self.W // 2, 14)
        self.box(rect, COLORS["panel"], 235, 12, COLORS["accent"], 2)
        fill = pygame.Rect(rect.x + 4, rect.y + 4, int((rect.w - 8) * progress), rect.h - 8)
        pygame.draw.rect(self.screen, COLORS["accent"], fill, border_radius=8)
        self.text("<<  " + label, 24, COLORS["text"], rect.center, "center", True)
