"""Gesture Tic-Tac-Toe - single entry point.

Run:  python main.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime

import pygame

from src.audio_manager import AudioManager
from src.camera import Camera, CameraError
from src.config import Config, ROOT, tr, X
from src.game_state import Game, State, MoveResult
from src.face_tracker import FaceTracker
from src.gesture_detector import (WinkDetector, is_wink, DwellSelector, HoldDetector, is_middle_pinch, is_start_sign, PointSmoother, SwipeBackDetector, cell_from_point,
                                  classify_gesture, index_extended, is_open_palm, pick_active_hand,
                                  pointer_for)
from src.hand_tracker import HandTracker
from src.renderer import Button, Renderer, COLORS, THEME_NAMES, make_icon
from src.stats import Stats


class App:
    def __init__(self) -> None:
        self.cfg = Config.load()
        pygame.init()
        pygame.display.set_caption("Gesture Tic-Tac-Toe")
        pygame.display.set_icon(make_icon())
        self.screen = pygame.display.set_mode(self.cfg.window_size)
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self.screen, self.cfg)
        self.audio = AudioManager(self.cfg.sound)
        self.camera = Camera(self.cfg)
        self.tracker = None
        self.face = None                                       # FaceTracker (wink = exit)
        self.wink = WinkDetector(1)
        self.exit_progress = 0.0
        self.ears = None
        self._frame_no = 0
        self._face_error = False
        self.stats = Stats.load()
        self.game = Game(self.cfg, self.stats)

        self.smoother = PointSmoother(self.cfg.smoothing)
        self.swipe = SwipeBackDetector()                       # open palm + swipe left = back
        self.back_progress = 0.0
        self.start_hold = HoldDetector(0.01)                    # rock sign (thumb+index+pinky) = start
        self.start_progress = 0.0
        self.click_hold = HoldDetector(0.01)                   # thumb + middle finger = click
        self.frozen_pos = None
        self.dwell = DwellSelector(self.cfg.dwell_time, self.cfg.dwell_grace)        # board cells

        self.running = True
        self.editing = None                 # index of the player name being typed, or None
        self.mouse_pos = None
        self.mouse_time = -99.0
        self.using_mouse = False

        # per-frame values
        self.hands = []
        self.active_hand = None
        self.cursor = None
        self.target = None
        self.progress = 0.0
        self.status = ""
        self.hover_symbol = None
        self.hover_ok = True
        self.buttons = []
        self.hover = None
        self.ui_progress = 0.0
        self.setup_progress = 0.0
        self._last_target = None
        self.timer_left = None
        self._last_cd = ""
        self._last_warn = None
        self._cam_fail_since = None
        self._cam_retry_at = 0.0

    # ======================================================= start-up
    def error_screen(self, message: str) -> bool:
        """Friendly error page. Returns True if the user pressed R (retry)."""
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return False
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_r:
                        return True
                    if e.key == pygame.K_ESCAPE:
                        return False
            self.renderer.draw_error(message)
            self.clock.tick(15)

    def start_hardware(self) -> bool:
        while True:                                    # FR-01: check webcam before the game
            try:
                self.camera.open()
                break
            except CameraError as exc:
                if not self.error_screen(str(exc)):
                    return False
        try:
            self.tracker = HandTracker()
        except Exception as exc:                       # missing model / offline / bad install
            self.error_screen(f"Could not start hand tracking.\n{exc}\nPress ESC to exit.")
            return False
        self.start_face()
        return True

    def start_face(self) -> bool:
        """Face tracking draws the mesh; wink-exit can be independently disabled."""
        if self.face is not None:
            return True
        try:
            self.face = FaceTracker()
            self._face_error = False
            return True
        except Exception as exc:
            print("Face tracking unavailable:", exc)
            self.face, self._face_error = None, True
            return False

    # ======================================================== buttons
    def build_buttons(self) -> list:
        g, cfg = self.game, self.cfg
        W = cfg.window_size[0]
        t = g.t
        B = []

        def col(items, x, y0, w, h, gap):
            for i, (bid, label) in enumerate(items):
                B.append(Button(bid, label, pygame.Rect(x, y0 + i * (h + gap), w, h)))

        if g.state is State.MENU:
            col([("play_ai", t("play_ai")), ("play_pvp", t("play_pvp")), ("stats", t("stats")),
                 ("instructions", t("instructions")), ("settings", t("settings")),
                 ("exit", t("exit"))], (W - 420) // 2, 215, 420, 58, 14)
        elif g.state is State.DIFFICULTY:
            for i, (bid, tint) in enumerate((("easy", "good"), ("medium", "accent"), ("hard", "bad"))):
                B.append(Button(bid, t(bid), pygame.Rect((W - 420) // 2, 225 + i * 92, 420, 72), tint))
            B.append(Button("menu", t("back"), pygame.Rect((W - 420) // 2, 225 + 3 * 92, 420, 62)))
        elif g.state is State.STATS:
            B.append(Button("reset_stats", t("reset_stats"), pygame.Rect(W // 2 - 330, 595, 310, 60)))
            B.append(Button("menu", t("back"), pygame.Rect(W // 2 + 20, 595, 310, 60)))
        elif g.state is State.PAUSED:
            col([("resume", t("resume")), ("restart", t("restart")), ("menu", t("menu"))],
                (W - 400) // 2, 235, 400, 64, 18)
        elif g.state is State.INSTRUCTIONS:
            col([("menu", t("back"))], (W - 300) // 2, 600, 300, 62, 0)
        elif g.state is State.SETTINGS:
            onoff = lambda v: t("on") if v else t("off")
            n = list(cfg.player_names)
            if self.editing is not None:
                n[self.editing] += "_"
            target = t("endless") if cfg.match_target == 0 else t("target_first", n=cfg.match_target)
            timer = t("timer_off") if cfg.turn_timer == 0 else t("timer_s", n=cfg.turn_timer)
            col([("dwell", t("dwell", v=cfg.dwell_time)),
                 ("symgest", t("symgest", v=onoff(cfg.symbol_gestures))),
                 ("zones", t("zones", v=onoff(cfg.use_player_zones))),
                 ("first", t("first", v=cfg.player_names[cfg.first_player])),
                 ("name1", t("name1", v=n[0])),
                 ("name2", t("name2", v=n[1])),
                 ("lang", t("lang", v=cfg.language.upper()))], 70, 105, 560, 52, 8)
            col([("match", t("target", v=target)),
                 ("timer", t("timer", v=timer)),
                 ("countdown", t("countdown", v=onoff(cfg.countdown))),
                 ("theme", t("theme", v=cfg.theme.capitalize())),
                 ("wink", t("wink", v=onoff(cfg.wink_exit))),
                 ("sound", t("sound", v=onoff(cfg.sound))),
                 ("debug", t("debug", v=onoff(cfg.debug)))], 650, 105, 560, 52, 8)
            B.append(Button("menu", t("back"), pygame.Rect((W - 300) // 2, 585, 300, 56)))
        elif g.state is State.ROUND_RESULT:
            if g.match_winner is not None:
                col([("new_round", t("rematch")), ("menu", t("menu"))], 730, 430, 470, 62, 14)
            else:
                col([("new_round", t("new_round")), ("reset_score", t("reset_score")),
                     ("menu", t("menu"))], 730, 430, 470, 58, 12)
        return B

    def activate(self, action: str, now: float) -> None:
        g, cfg = self.game, self.cfg
        if action in ("start", "quick_start"):        # keep the last mode / difficulty
            g.start_match()
        elif action == "play_ai":
            g.go(State.DIFFICULTY)
        elif action == "play_pvp":
            cfg.mode = "pvp"
            g.start_match()
        elif action in ("easy", "medium", "hard"):
            cfg.mode, cfg.ai_level = "ai", action
            g.start_match()
        elif action == "stats":
            g.go(State.STATS)
        elif action == "reset_stats":
            self.stats.reset()
            g.flash(g.t("reset_stats") + " OK", now)
        elif action == "resume":
            g.resume()
        elif action == "restart":
            g.restart_round()
        elif action == "match":
            opts = [0, 2, 3, 5]
            cfg.match_target = opts[(opts.index(cfg.match_target) + 1) % len(opts)] if cfg.match_target in opts else 3
        elif action == "timer":
            opts = [0, 10, 15, 20]
            cfg.turn_timer = opts[(opts.index(cfg.turn_timer) + 1) % len(opts)] if cfg.turn_timer in opts else 0
        elif action == "wink":
            cfg.wink_exit = not cfg.wink_exit
            self.wink.reset()
            if cfg.wink_exit and not self.start_face():
                cfg.wink_exit = False
                g.flash(g.t("face_fail"), now)
        elif action == "countdown":
            cfg.countdown = not cfg.countdown
        elif action == "theme":
            i = THEME_NAMES.index(cfg.theme) if cfg.theme in THEME_NAMES else 0
            cfg.theme = THEME_NAMES[(i + 1) % len(THEME_NAMES)]
            self.renderer.set_theme(cfg.theme)
        elif action == "instructions":
            g.go(State.INSTRUCTIONS)
        elif action == "settings":
            g.go(State.SETTINGS)
        elif action == "exit":
            self.running = False
        elif action == "new_round":
            g.new_round()
        elif action == "reset_score":
            g.reset_score()
        elif action == "menu":
            self.editing = None
            cfg.save()
            g.to_menu()
        elif action == "dwell":
            options = [0.8, 1.0, 1.2, 1.5]
            nearest = min(range(4), key=lambda i: abs(options[i] - cfg.dwell_time))
            cfg.dwell_time = options[(nearest + 1) % 4]
            self.dwell.dwell_time = cfg.dwell_time
        elif action == "symgest":
            cfg.symbol_gestures = not cfg.symbol_gestures
        elif action == "zones":
            cfg.use_player_zones = not cfg.use_player_zones
        elif action == "first":
            cfg.first_player = 1 - cfg.first_player
            g.round_starter = cfg.first_player
        elif action == "debug":
            cfg.debug = not cfg.debug
        elif action == "sound":
            cfg.sound = not cfg.sound
            self.audio.enabled = cfg.sound
        elif action == "lang":
            if cfg.language == "en":
                if self.renderer.has_khmer_font():
                    cfg.language = "km"
                else:
                    g.flash("Put a Khmer .ttf font in assets/fonts first", now)
            else:
                cfg.language = "en"
            self.renderer.reload_fonts()
        elif action in ("name1", "name2"):
            self.editing = 0 if action == "name1" else 1
        self.dwell.reset()

    def go_back(self, now: float) -> None:
        """Back gesture / ESC: pause while playing, resume from pause, otherwise to the menu."""
        g = self.game
        if g.state is State.PLAYING:
            g.pause()
            self.dwell.reset()
        elif g.state is State.PAUSED:
            self.activate("menu", now)
        else:
            self.activate("menu", now)

    def screenshot(self, now: float) -> None:
        folder = ROOT / "screenshots"
        try:
            folder.mkdir(exist_ok=True)
            pygame.image.save(self.screen, str(folder / f"tictactoe_{datetime.now():%Y%m%d_%H%M%S}.png"))
            self.game.flash(self.game.t("saved"), now)
        except (OSError, pygame.error):
            pass

    def after_move(self, result, now: float) -> None:
        """Sound + effects for a move made by a player, the timer or the computer."""
        g, cfg = self.game, self.cfg
        sound = {MoveResult.PLACED: "place", MoveResult.OCCUPIED: "invalid",
                 MoveResult.WIN: "win", MoveResult.DRAW: "draw"}.get(result)
        if result is MoveResult.WIN:
            human_lost = cfg.mode == "ai" and g.turns.current_index == 1
            if g.match_winner is not None:
                sound = "draw" if human_lost else "match"
                if not human_lost:
                    self.renderer.burst_confetti(260)
            elif human_lost:
                sound = "draw"
            else:
                self.renderer.burst_confetti(130)
        if sound:
            self.audio.play(sound)
        if result in (MoveResult.WIN, MoveResult.DRAW):
            self.dwell.reset()
            self._last_target = None

    # ========================================================= events
    def handle_events(self, now: float) -> None:
        g = self.game
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.MOUSEMOTION:
                self.mouse_pos, self.mouse_time = e.pos, now
            elif e.type == pygame.KEYDOWN:
                if self.editing is not None:                     # typing a player name
                    names = self.cfg.player_names
                    i = self.editing
                    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                        if not names[i].strip():
                            names[i] = f"Player {i + 1}"
                        self.editing = None
                    elif e.key == pygame.K_BACKSPACE:
                        names[i] = names[i][:-1]
                    elif e.unicode and e.unicode.isprintable() and len(names[i]) < 14:
                        names[i] += e.unicode
                    g.sync_names()
                    continue
                if e.key == pygame.K_ESCAPE:
                    if g.state is State.MENU:
                        self.running = False
                    elif g.state is State.PLAYING:
                        g.pause()
                        self.dwell.reset()
                    elif g.state is State.PAUSED:
                        g.resume()
                    else:
                        self.cfg.save()
                        g.to_menu()
                elif e.key == pygame.K_p and g.state in (State.PLAYING, State.PAUSED):
                    g.pause() if g.state is State.PLAYING else g.resume()
                    self.dwell.reset()
                elif e.key == pygame.K_h and g.state is State.PLAYING:
                    if g.show_hint(now) is None:
                        g.flash(g.t("no_hint"), now)
                elif e.key == pygame.K_s:
                    self.screenshot(now)
                elif e.key == pygame.K_r and g.state is State.PLAYING:
                    g.restart_round()
                elif e.key in (pygame.K_r, pygame.K_n) and g.state is State.ROUND_RESULT:
                    g.new_round()
                elif e.key == pygame.K_SPACE and g.state is State.SETUP:
                    g.start_round()
                elif e.key == pygame.K_d:
                    self.cfg.debug = not self.cfg.debug
                elif e.key == pygame.K_m:
                    self.cfg.sound = not self.cfg.sound
                    self.audio.enabled = self.cfg.sound

    # ========================================================= update
    def update(self, now: float, hands) -> None:
        g, cfg = self.game, self.cfg
        self.hands = hands
        self.active_hand = None
        self.target = None
        self.progress = 0.0
        self.hover = None
        self.ui_progress = 0.0
        self.status = ""
        self.hover_symbol = None
        self.hover_ok = True
        self.timer_left = None

        # WINK held ~1.2 s -> quit (works on every screen)
        self.exit_progress = 0.0
        if cfg.wink_exit and self.face is not None:
            self.exit_progress, quit_now = self.wink.update(self.ears, now)
            if quit_now:
                self.audio.play("match")
                pygame.time.wait(350)                          # let the goodbye sound start
                self.running = False
                return
        else:
            self.wink.reset()

        # open palm swiped to the left -> back to the menu (works in every screen except the menu)
        self.start_progress = 0.0
        if g.state is State.MENU:
            self.swipe.reset()
            self.back_progress = 0.0
            sign = any(is_start_sign(h.landmarks) for h in hands)
            self.start_progress, go = self.start_hold.update(sign, now)
            if go:
                self.audio.play("place")
                self.start_hold.reset()
                self.activate("quick_start", now)
                self.smoother.reset()
                return
        else:
            self.start_hold.reset()
            palm = next((h for h in hands if is_open_palm(h.landmarks)), None)
            self.back_progress, back = self.swipe.update(palm.landmarks if palm else None, now)
            if back:
                self.audio.play("place")
                self.go_back(now)
                self.back_progress = 0.0
                self.smoother.reset()
                return

        if g.state is State.PLAYING:
            self.update_playing(now)
        elif g.state is State.SETUP:
            self.cursor = None
            self.setup_progress = g.tick_setup(bool(hands), now)
        else:
            self.update_ui(now)

    def update_playing(self, now: float) -> None:
        g, cfg = self.game, self.cfg
        W, H = cfg.window_size
        ai_turn = g.is_ai_turn()                              # the computer moves by itself
        live = g.countdown_left(now) <= 0                     # 3-2-1 countdown still running?
        zones = cfg.use_player_zones and cfg.mode == "pvp"
        hand = None if ai_turn else pick_active_hand(self.hands, g.turns.current_index, zones)
        self.active_hand = hand
        tip = None
        sym = None                                            # symbol shown by the hand
        current = g.turns.current
        if ai_turn:
            self.status = g.t("thinking")
        elif hand is None:
            self.status = g.t("no_hand", name=current.name)
        elif cfg.symbol_gestures:
            sym = classify_gesture(hand.landmarks)            # X = index+thumb, O = index only
            if sym is None:                                   # ambiguous gesture -> ignored
                self.status = g.t("gesture_help")
            else:
                px, py = pointer_for(hand.landmarks, sym)
                tip = (px * W, py * H)
        elif not index_extended(hand.landmarks):              # classic mode: any pointing finger
            self.status = g.t("fist")
        else:
            sym = current.symbol
            tip = (hand.tip[0] * W, hand.tip[1] * H)

        self.hover_symbol = sym
        self.hover_ok = sym is None or sym == current.symbol
        if sym is not None and not self.hover_ok:             # right hand, wrong player's gesture
            self.status = g.t("wrong_gesture", symbol=current.symbol, gesture=g.t("gesture_" + current.symbol))

        self.cursor = self.smoother.update(tip)
        target = cell_from_point(self.cursor, cfg.board_rect, deadzone=cfg.cell_deadzone)
        self.target = target
        if target is not None and target != self._last_target:
            self.audio.play("target")
        if target is not None:
            self._last_target = target
        elif self.cursor is None:
            self._last_target = None

        # countdown sounds
        label, _ = g.countdown_label(now)
        if label != self._last_cd:
            if label:
                self.audio.play("tick" if label.isdigit() else "go")
            self._last_cd = label

        if not live:                                          # nothing can be placed during 3-2-1
            self.target, self.hover_symbol = None, None
            self.dwell.reset()
            return

        self.progress, confirmed = self.dwell.update(target if self.hover_ok and not ai_turn else None, now)
        if confirmed is not None:
            self.after_move(g.try_place(confirmed, now), now)
            return

        result = g.tick(now)                                   # computer move / turn-timer timeout
        if result is not None:
            self.after_move(result, now)

        self.timer_left = g.turn_time_left(now)                # warning ticks for the last 3 s
        if self.timer_left is not None and self.timer_left <= 3:
            sec = int(self.timer_left) + 1
            if sec != self._last_warn:
                self.audio.play("warn")
                self._last_warn = sec
        else:
            self._last_warn = None

    def update_ui(self, now: float) -> None:
        cfg = self.cfg
        W, H = cfg.window_size
        self.using_mouse = self.mouse_pos is not None and now - self.mouse_time < 3.0
        hand = next((h for h in self.hands if not is_open_palm(h.landmarks)), None)
        pinching = hand is not None and is_middle_pinch(hand.landmarks)
        self.ui_progress, clicked = self.click_hold.update(pinching, now)
        if self.using_mouse:
            pos = self.mouse_pos
            self.smoother.reset()
        else:
            if pinching and self.frozen_pos is not None:
                pos = self.frozen_pos              # keep the cursor still while clicking
            else:
                tip = (hand.tip[0] * W, hand.tip[1] * H) if hand else None
                pos = self.smoother.update(tip)
                self.frozen_pos = pos
        self.cursor = pos

        hover = None
        if pos is not None:
            for i, b in enumerate(self.buttons):
                if b.rect.collidepoint(pos):
                    hover = i
                    break
        self.hover = hover
        if clicked and hover is not None and hover < len(self.buttons):
            self.audio.play("place")
            self.activate(self.buttons[hover].id, now)        # thumb + middle finger click

    # =========================================================== draw
    def draw(self, now: float) -> None:
        r, g, cfg = self.renderer, self.game, self.cfg
        r.draw_background()
        r.draw_face_mesh(self.face.landmarks if self.face is not None else ())
        r.draw_hands(self.hands, self.active_hand)
        st = g.state
        pcolor = r.player_color(g.turns.current_index)

        if st is State.MENU:
            r.draw_menu(self.buttons, self.hover, self.ui_progress, now)
        elif st is State.DIFFICULTY:
            r.draw_difficulty(self.buttons, self.hover, self.ui_progress, now)
        elif st is State.STATS:
            r.draw_stats(self.stats, g, self.buttons, self.hover, self.ui_progress, now)
        elif st is State.INSTRUCTIONS:
            r.draw_instructions(self.buttons, self.hover, self.ui_progress)
        elif st is State.SETTINGS:
            r.draw_settings(self.buttons, self.hover, self.ui_progress)
        elif st is State.SETUP:
            r.draw_setup(self.setup_progress)
        else:
            if cfg.use_player_zones:
                r.draw_zones()
            playing = st is State.PLAYING
            r.draw_board(g, self.target if playing else None, self.progress, now,
                         self.hover_symbol if playing else None, self.hover_ok)
            r.draw_side_panel(g, now, self.status, self.timer_left)
            if playing:
                r.draw_countdown(*g.countdown_label(now))
            if st is State.ROUND_RESULT:
                r.draw_buttons(self.buttons, self.hover, self.ui_progress)
            elif st is State.PAUSED:
                r.draw_pause(self.buttons, self.hover, self.ui_progress)
            r.draw_confetti(self.clock.get_time() / 1000.0)

        if g.message and now < g.message_until:
            r.draw_message(g.message)
        r.draw_exit_progress(self.exit_progress, g.t("wink_label"))
        if cfg.debug:
            r.draw_fps(self.clock.get_fps())
            if self.ears is not None:
                r.text(f"eyes {self.ears[0]:.2f} / {self.ears[1]:.2f}" + ("  WINK" if is_wink(self.ears) else ""),
                       20, COLORS["muted"], (14, self.H - 60), "bottomleft")
        if self._cam_fail_since is not None and now - self._cam_fail_since > 1.0:
            r.draw_banner(g.t("cam_lost"))

        if st is State.MENU:
            r.draw_footer(g.t("menu_hint"))
            r.draw_start_progress(self.start_progress, g.t("start_label"))
        else:
            if st in (State.PLAYING, State.PAUSED, State.ROUND_RESULT):
                r.draw_footer_left(g.t("pause_hint"))
            r.draw_footer(g.t("swipe_hint"))
            r.draw_back_progress(self.back_progress, g.t("back_label"))

        if st is State.PLAYING:
            r.draw_cursor(self.cursor, pcolor)
        else:
            r.draw_cursor(self.cursor, COLORS["accent"], self.ui_progress)

    # ============================================================ run
    def run(self) -> None:
        self.renderer.draw_splash(self.game.t("starting"), time.perf_counter())
        if not self.start_hardware():
            return
        if self._face_error:                                   # game still works, just without wink-exit
            self.game.flash(self.game.t("face_fail"), time.perf_counter())
        try:
            while self.running:
                now = time.perf_counter()
                self.handle_events(now)
                self.buttons = self.build_buttons()

                frame = self.camera.read()
                if frame is None:                              # FR-14: camera hiccup, never crash
                    if self._cam_fail_since is None:
                        self._cam_fail_since = now
                    if now - self._cam_fail_since > 1.0:
                        self.renderer.set_frame(None)
                    if now - self._cam_fail_since > 3.0 and now > self._cam_retry_at:
                        self._cam_retry_at = now + 3.0
                        try:
                            self.camera.open()
                        except CameraError:
                            pass
                    hands = []
                    self.ears = None
                    if self.face is not None:
                        self.face.landmarks = []
                else:
                    self._cam_fail_since = None
                    self.renderer.set_frame(frame)
                    hands = self.tracker.process(frame)        # [] when no hand: handled everywhere
                    self._frame_no += 1
                    if self.face is not None and self._frame_no % 2 == 0:
                        self.ears = self.face.process(frame)   # every 2nd frame is plenty for a 1 s hold

                self.update(now, hands)
                self.draw(now)
                pygame.display.flip()
                self.clock.tick(self.cfg.fps_limit)
        finally:                                               # safe exit
            self.cfg.save()
            if self.tracker:
                self.tracker.close()
            if self.face:
                self.face.close()
            self.camera.release()
            pygame.quit()


def main() -> int:
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
