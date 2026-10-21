"""Lifetime statistics, saved to stats.json (in-memory only when path is None)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .config import ROOT

STATS_FILE = ROOT / "stats.json"


def _blank() -> dict:
    return {
        "rounds": 0, "streak": 0, "best_streak": 0, "matches_won": 0, "matches_lost": 0,
        "ai": {lvl: {"w": 0, "l": 0, "d": 0} for lvl in ("easy", "medium", "hard")},
        "pvp": {"p1": 0, "p2": 0, "d": 0},
    }


class Stats:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path
        self.data = _blank()

    # ------------------------------------------------------------ persistence
    @classmethod
    def load(cls, path: Path = STATS_FILE) -> "Stats":
        s = cls(path)
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return s
        if isinstance(raw, dict):
            for key, value in raw.items():
                if key in s.data and isinstance(value, type(s.data[key])):
                    if isinstance(value, dict):
                        for k2, v2 in value.items():
                            if k2 in s.data[key]:
                                s.data[key][k2] = v2
                    else:
                        s.data[key] = value
        return s

    def save(self) -> None:
        if self.path is None:
            return
        try:
            Path(self.path).write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def reset(self) -> None:
        self.data = _blank()
        self.save()

    # -------------------------------------------------------------- recording
    def record_round(self, mode: str, level: str, winner: Optional[int]) -> None:
        """winner: 0 = Player 1 / human, 1 = Player 2 / computer, None = draw."""
        d = self.data
        d["rounds"] += 1
        if mode == "ai":
            row = d["ai"].setdefault(level, {"w": 0, "l": 0, "d": 0})
            if winner is None:
                row["d"] += 1
            elif winner == 0:
                row["w"] += 1
                d["streak"] += 1
                d["best_streak"] = max(d["best_streak"], d["streak"])
            else:
                row["l"] += 1
                d["streak"] = 0
        else:
            if winner is None:
                d["pvp"]["d"] += 1
            else:
                d["pvp"]["p1" if winner == 0 else "p2"] += 1
        self.save()

    def record_match(self, mode: str, winner: int) -> None:
        if mode == "ai":
            self.data["matches_won" if winner == 0 else "matches_lost"] += 1
            self.save()

    # ---------------------------------------------------------------- queries
    def ai_totals(self):
        w = sum(r["w"] for r in self.data["ai"].values())
        l = sum(r["l"] for r in self.data["ai"].values())
        d = sum(r["d"] for r in self.data["ai"].values())
        return w, l, d
