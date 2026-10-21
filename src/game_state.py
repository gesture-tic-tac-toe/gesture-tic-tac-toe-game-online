"""Game state manager: menu / setup / playing / result flow + round logic.

It knows nothing about cameras or drawing - input arrives as "try_place(cell)".
That keeps the rules reusable for mouse, touch, pinch or an AI opponent later.
"""
from __future__ import annotations

import random
from enum import Enum
from typing import Dict, Optional, Tuple

from .ai import best_move, choose_move
from .board import Board
from .config import Config, tr
from .game_rules import evaluate, WIN, DRAW
from .score_manager import ScoreManager
from .stats import Stats
from .turn_manager import TurnManager, make_players


class State(Enum):
    MENU = "menu"
    INSTRUCTIONS = "instructions"
    SETTINGS = "settings"
    DIFFICULTY = "difficulty"
    STATS = "stats"
    PAUSED = "paused"
    SETUP = "setup"
    PLAYING = "playing"
    CHECK_RESULT = "check_result"
    ROUND_RESULT = "round_result"


class MoveResult(Enum):
    IGNORED = 0     # not in PLAYING state / bad cell
    OCCUPIED = 1    # invalid move
    PLACED = 2      # valid, game continues
    WIN = 3
    DRAW = 4


class Game:
    SETUP_HOLD = 0.8      # seconds a hand must be visible before the round starts
    MESSAGE_TIME = 1.6
    COUNT_STEP = 0.8      # seconds per number of the 3-2-1 countdown
    GO_TIME = 0.5         # how long "GO!" stays on screen
    AI_DELAY = (0.6, 1.1) # the computer "thinks" for a moment so it feels natural
    HINT_TIME = 2.0

    def __init__(self, cfg: Config, stats: Optional[Stats] = None) -> None:
        self.cfg = cfg
        self.stats = stats if stats is not None else Stats(None)   # None = in-memory (tests)
        self.match_winner: Optional[int] = None
        self.hint_cell: Optional[int] = None
        self.hint_until = 0.0
        self._turn_start: Optional[float] = None
        self._ai_ready_at: Optional[float] = None
        self._cd_armed = False
        self._cd_end: Optional[float] = None
        self.board = Board()
        self.players = make_players(cfg.player_names)
        self.turns = TurnManager(self.players, cfg.first_player)
        self.scores = ScoreManager()
        self.state = State.MENU
        self.outcome = None
        self.round_starter = cfg.first_player
        self.placed_at: Dict[int, float] = {}
        self.message = ""
        self.message_until = 0.0
        self.result_at = 0.0
        self._setup_since: Optional[float] = None
        self.sync_names()

    # ------------------------------------------------------------ helpers
    def t(self, key: str, **kw):
        return tr(self.cfg.language, key, **kw)

    def flash(self, text: str, now: float) -> None:
        self.message = text
        self.message_until = now + self.MESSAGE_TIME

    def go(self, state: State) -> None:
        self.state = state
        self._setup_since = None

    def sync_names(self) -> None:
        for i in (0, 1):
            self.players[i].name = self.cfg.player_names[i]
        if self.cfg.mode == "ai":
            self.players[1].name = self.t("computer")

    # ------------------------------------------------------- mode helpers
    def is_ai_turn(self) -> bool:
        return (self.state is State.PLAYING and self.cfg.mode == "ai"
                and self.turns.current_index == 1)

    def _new_turn(self) -> None:
        self._turn_start = None
        self._ai_ready_at = None
        self.hint_cell = None

    # ------------------------------------------------------------- flow
    def start_match(self) -> None:
        self.scores.reset()
        self.match_winner = None
        self.sync_names()
        self.round_starter = self.cfg.first_player
        self.board.reset()
        self.outcome = None
        self.go(State.SETUP)

    def start_round(self) -> None:
        self.board.reset()
        self.placed_at.clear()
        self.outcome = None
        self.turns.set_first(self.round_starter)
        self._new_turn()
        self._cd_armed = self.cfg.countdown
        self._cd_end = None
        self.go(State.PLAYING)

    def restart_round(self) -> None:
        """Clear the board, keep the score and the same starter."""
        self.start_round()

    def new_round(self) -> None:
        if self.match_winner is not None:                  # rematch after a finished match
            self.scores.reset()
            self.match_winner = None
        if self.cfg.alternate_first:
            self.round_starter = 1 - self.round_starter
        if not self.cfg.preserve_score:
            self.scores.reset()
        self.start_round()

    def reset_score(self) -> None:
        self.scores.reset()
        self.match_winner = None

    # -------------------------------------------------------------- pause
    def pause(self) -> bool:
        if self.state is not State.PLAYING:
            return False
        self._new_turn()
        self._cd_end = None
        self._cd_armed = False
        self.state = State.PAUSED
        return True

    def resume(self) -> None:
        if self.state is State.PAUSED:
            self._new_turn()
            self.state = State.PLAYING

    # ---------------------------------------------------------- countdown
    def countdown_left(self, now: float) -> float:
        """Seconds of the 3-2-1 countdown still to run (0 = round is live)."""
        if self.state is not State.PLAYING:
            return 0.0
        if self._cd_armed:
            self._cd_armed = False
            self._cd_end = now + 3 * self.COUNT_STEP
        if self._cd_end is None:
            return 0.0
        return max(0.0, self._cd_end - now)

    def countdown_label(self, now: float) -> Tuple[str, float]:
        """('3' | '2' | '1' | 'GO!' | '', progress 0..1 inside the current label)."""
        left = self.countdown_left(now)
        if left > 0:
            idx = min(2, int((left - 1e-9) / self.COUNT_STEP))      # 2,1,0
            within = left - idx * self.COUNT_STEP
            return str(idx + 1), 1 - within / self.COUNT_STEP
        if self._cd_end is not None and now - self._cd_end < self.GO_TIME:
            return self.t("go"), (now - self._cd_end) / self.GO_TIME
        return "", 0.0

    # --------------------------------------------------- timer / AI / hint
    def turn_time_left(self, now: float) -> Optional[float]:
        limit = self.cfg.turn_timer
        if limit <= 0 or self.state is not State.PLAYING or self.is_ai_turn():
            return None
        if self._turn_start is None:
            self._turn_start = now
        return max(0.0, limit - (now - self._turn_start))

    def tick(self, now: float) -> Optional[MoveResult]:
        """Call every frame while PLAYING (after the countdown). Plays the computer's move
        and handles the turn-timer timeout. Returns the MoveResult if a move was made."""
        if self.state is not State.PLAYING:
            return None
        if self.is_ai_turn():
            if self._ai_ready_at is None:
                self._ai_ready_at = now + random.uniform(*self.AI_DELAY)
            if now < self._ai_ready_at:
                return None
            cell = choose_move(self.board.flat(), self.turns.current.symbol, self.cfg.ai_level)
            return self.try_place(cell, now) if cell is not None else None
        left = self.turn_time_left(now)
        if left is not None and left <= 0:
            free = self.board.empty_cells()
            if free:
                self.flash(self.t("timeup"), now)
                return self.try_place(random.choice(free), now)
        return None

    def show_hint(self, now: float) -> Optional[int]:
        if self.state is not State.PLAYING or self.is_ai_turn():
            return None
        cell = best_move(self.board.flat(), self.turns.current.symbol)
        if cell is None:
            return None
        self.hint_cell, self.hint_until = cell, now + self.HINT_TIME
        return cell

    def to_menu(self) -> None:
        self.go(State.MENU)

    def tick_setup(self, hand_visible: bool, now: float) -> float:
        """SETUP state: start the round once a hand has been visible for SETUP_HOLD s.
        Returns progress 0..1 for the UI."""
        if self.state is not State.SETUP:
            return 0.0
        if not hand_visible:
            self._setup_since = None
            return 0.0
        if self._setup_since is None:
            self._setup_since = now
        progress = min(1.0, (now - self._setup_since) / self.SETUP_HOLD)
        if progress >= 1.0:
            self.start_round()
        return progress

    # -------------------------------------------------------------- moves
    def try_place(self, cell: int, now: float) -> MoveResult:
        if self.state is not State.PLAYING or not Board.valid_cell(cell):
            return MoveResult.IGNORED
        player = self.turns.current
        if not self.board.place(cell, player.symbol):
            self.flash(self.t("occupied"), now)
            return MoveResult.OCCUPIED          # stays PLAYING, same player's turn
        self.placed_at[cell] = now
        self.state = State.CHECK_RESULT
        self.outcome = evaluate(self.board)
        self._new_turn()
        if self.outcome.status == WIN:
            idx = self.turns.current_index
            self.scores.record_win(idx)
            self.stats.record_round(self.cfg.mode, self.cfg.ai_level, idx)
            target = self.cfg.match_target
            if target > 0 and self.scores.wins[idx] >= target:
                self.match_winner = idx
                self.stats.record_match(self.cfg.mode, idx)
            self.result_at = now
            self.state = State.ROUND_RESULT
            return MoveResult.WIN
        if self.outcome.status == DRAW:
            self.scores.record_draw()
            self.stats.record_round(self.cfg.mode, self.cfg.ai_level, None)
            self.result_at = now
            self.state = State.ROUND_RESULT
            return MoveResult.DRAW
        self.turns.switch()                      # switch only after a VALID move
        self.state = State.PLAYING
        return MoveResult.PLACED

    # ------------------------------------------------------------- text
    def result_text(self) -> str:
        if self.outcome is None:
            return ""
        if self.match_winner is not None:
            return self.t("match_winner", name=self.players[self.match_winner].name)
        if self.outcome.status == WIN:
            winner = next(p for p in self.players if p.symbol == self.outcome.symbol)
            return self.t("wins", name=winner.name)
        return self.t("draw")
