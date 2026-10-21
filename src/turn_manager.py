"""Turn management. Player 1 is always X, Player 2 is always O."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .config import X, O


@dataclass
class Player:
    name: str
    symbol: str


def make_players(names) -> List[Player]:
    return [Player(names[0], X), Player(names[1], O)]


class TurnManager:
    def __init__(self, players: List[Player], first: int = 0) -> None:
        self.players = players
        self.current_index = first if first in (0, 1) else 0

    @property
    def current(self) -> Player:
        return self.players[self.current_index]

    def switch(self) -> None:
        self.current_index = 1 - self.current_index

    def set_first(self, index: int) -> None:
        self.current_index = index if index in (0, 1) else 0
