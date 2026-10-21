import unittest

from src.score_manager import ScoreManager


class ScoreTests(unittest.TestCase):                             # Score Test
    def test_win_increments_only_winner(self):
        s = ScoreManager()
        s.record_win(1)
        s.record_win(1)
        s.record_win(0)
        self.assertEqual(s.wins, [1, 2])
        self.assertEqual(s.rounds_played, 3)

    def test_draw_changes_no_score(self):
        s = ScoreManager()
        s.record_draw()
        self.assertEqual(s.wins, [0, 0])
        self.assertEqual(s.draws, 1)

    def test_reset(self):
        s = ScoreManager()
        s.record_win(0)
        s.reset()
        self.assertEqual((s.wins, s.draws, s.rounds_played), ([0, 0], 0, 0))


if __name__ == "__main__":
    unittest.main()
