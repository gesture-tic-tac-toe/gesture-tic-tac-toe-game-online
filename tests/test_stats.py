import json
import tempfile
import unittest
from pathlib import Path

from src.stats import Stats


class StatsTests(unittest.TestCase):
    def test_ai_rounds_and_streak(self):
        s = Stats(None)
        for w in (0, 0, 0, 1, 0):
            s.record_round("ai", "hard", w)
        s.record_round("ai", "hard", None)
        self.assertEqual(s.data["ai"]["hard"], {"w": 4, "l": 1, "d": 1})
        self.assertEqual((s.data["streak"], s.data["best_streak"], s.data["rounds"]), (1, 3, 6))

    def test_pvp_rounds(self):
        s = Stats(None)
        s.record_round("pvp", "easy", 0)
        s.record_round("pvp", "easy", 1)
        s.record_round("pvp", "easy", None)
        self.assertEqual(s.data["pvp"], {"p1": 1, "p2": 1, "d": 1})
        self.assertEqual(s.ai_totals(), (0, 0, 0))

    def test_matches(self):
        s = Stats(None)
        s.record_match("ai", 0)
        s.record_match("ai", 1)
        s.record_match("pvp", 0)                     # not counted
        self.assertEqual((s.data["matches_won"], s.data["matches_lost"]), (1, 1))

    def test_save_load_and_reset(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "stats.json"
            s = Stats(path)
            s.record_round("ai", "easy", 0)
            again = Stats.load(path)
            self.assertEqual(again.data["ai"]["easy"]["w"], 1)
            again.reset()
            self.assertEqual(Stats.load(path).data["rounds"], 0)

    def test_corrupt_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "stats.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(Stats.load(path).data["rounds"], 0)
            path.write_text(json.dumps({"rounds": "oops", "ai": {"easy": {"w": 5}}}), encoding="utf-8")
            s = Stats.load(path)
            self.assertEqual(s.data["rounds"], 0)
            self.assertEqual(s.data["ai"]["easy"]["w"], 5)


if __name__ == "__main__":
    unittest.main()
