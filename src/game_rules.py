"""Rules engine: win / draw detection. Pure logic - no camera, no UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .board import Board

WIN_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),      # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),      # columns
    (0, 4, 8), (2, 4, 6),                 # diagonals
)

PLAYING, WIN, DRAW = "playing", "win", "draw"


@dataclass(frozen=True)
class Outcome:
    status: str
    symbol: Optional[str] = None
    line: Optional[Tuple[int, int, int]] = None


def evaluate(board: Board) -> Outcome:
    cells = board.flat()
    for line in WIN_LINES:
        a, b, c = line
        if cells[a] and cells[a] == cells[b] == cells[c]:
            return Outcome(WIN, cells[a], line)
    if board.is_full():
        return Outcome(DRAW)
    return Outcome(PLAYING)
