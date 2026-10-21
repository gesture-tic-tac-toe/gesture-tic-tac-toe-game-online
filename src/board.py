"""Board state model: a 3x3 grid of EMPTY / X / O."""
from __future__ import annotations

from .config import EMPTY, X, O

SIZE = 3


class Board:
    def __init__(self) -> None:
        self.grid = [[EMPTY] * SIZE for _ in range(SIZE)]

    @staticmethod
    def valid_cell(cell) -> bool:
        return isinstance(cell, int) and 0 <= cell < SIZE * SIZE

    def reset(self) -> None:
        self.grid = [[EMPTY] * SIZE for _ in range(SIZE)]

    def get(self, cell: int) -> str:
        if not self.valid_cell(cell):
            raise IndexError(cell)
        row, col = divmod(cell, SIZE)
        return self.grid[row][col]

    def is_empty(self, cell: int) -> bool:
        return self.valid_cell(cell) and self.get(cell) == EMPTY

    def place(self, cell: int, symbol: str) -> bool:
        """Place a symbol. Returns False (and changes nothing) if invalid or occupied."""
        if symbol not in (X, O) or not self.is_empty(cell):
            return False
        row, col = divmod(cell, SIZE)
        self.grid[row][col] = symbol
        return True

    def flat(self) -> list:
        return [c for row in self.grid for c in row]

    def empty_cells(self) -> list:
        return [i for i, c in enumerate(self.flat()) if c == EMPTY]

    def is_full(self) -> bool:
        return not self.empty_cells()
