"""Computer opponent. Pure logic - works on a flat list of 9 cells ("" / "X" / "O").

Levels
------
easy   : random move
medium : wins if it can, blocks if it must, otherwise takes centre / corner (with a few blunders)
hard   : full minimax with alpha-beta pruning -> never loses
"""
from __future__ import annotations

import random
from typing import List, Optional, Sequence

from .config import EMPTY, X, O
from .game_rules import WIN_LINES

LEVELS = ("easy", "medium", "hard")
CORNERS = (0, 2, 6, 8)


def other(symbol: str) -> str:
    return O if symbol == X else X


def winner_of(cells: Sequence[str]) -> Optional[str]:
    for a, b, c in WIN_LINES:
        if cells[a] and cells[a] == cells[b] == cells[c]:
            return cells[a]
    return None


def empty_cells(cells: Sequence[str]) -> List[int]:
    return [i for i, c in enumerate(cells) if c == EMPTY]


def _winning_move(cells: Sequence[str], symbol: str) -> Optional[int]:
    for i in empty_cells(cells):
        trial = list(cells)
        trial[i] = symbol
        if winner_of(trial) == symbol:
            return i
    return None


def _minimax(cells: List[str], turn: str, me: str, alpha: int, beta: int, depth: int) -> int:
    w = winner_of(cells)
    if w == me:
        return 10 - depth                 # faster wins score higher
    if w is not None:
        return depth - 10                 # slower losses score higher
    free = empty_cells(cells)
    if not free:
        return 0
    if turn == me:
        best = -99
        for i in free:
            cells[i] = turn
            best = max(best, _minimax(cells, other(turn), me, alpha, beta, depth + 1))
            cells[i] = EMPTY
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best
    best = 99
    for i in free:
        cells[i] = turn
        best = min(best, _minimax(cells, other(turn), me, alpha, beta, depth + 1))
        cells[i] = EMPTY
        beta = min(beta, best)
        if alpha >= beta:
            break
    return best


def best_move(cells: Sequence[str], symbol: str, rng: Optional[random.Random] = None) -> Optional[int]:
    """Perfect move for `symbol` (ties are broken randomly so games vary)."""
    rng = rng or random
    free = empty_cells(cells)
    if not free:
        return None
    work = list(cells)
    scored = []
    for i in free:
        work[i] = symbol
        scored.append((_minimax(work, other(symbol), symbol, -99, 99, 1), i))
        work[i] = EMPTY
    top = max(s for s, _ in scored)
    return rng.choice([i for s, i in scored if s == top])


def choose_move(cells: Sequence[str], symbol: str, level: str = "medium",
                rng: Optional[random.Random] = None) -> Optional[int]:
    rng = rng or random
    free = empty_cells(cells)
    if not free:
        return None
    if level == "hard":
        return best_move(cells, symbol, rng)
    if level == "easy":
        return rng.choice(free)
    # medium
    if rng.random() < 0.15:                                   # occasional blunder keeps it beatable
        return rng.choice(free)
    for sym in (symbol, other(symbol)):                       # win first, then block
        m = _winning_move(cells, sym)
        if m is not None:
            return m
    if 4 in free:
        return 4
    corners = [c for c in CORNERS if c in free]
    return rng.choice(corners or free)
