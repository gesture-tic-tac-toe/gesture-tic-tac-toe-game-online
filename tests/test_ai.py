import random
import unittest

from src.ai import best_move, choose_move, empty_cells, other, winner_of
from src.config import X, O


def play(level_x, level_o, seed):
    rng = random.Random(seed)
    cells, turn = [""] * 9, X
    levels = {X: level_x, O: level_o}
    while True:
        cells[choose_move(cells, turn, levels[turn], rng)] = turn
        w = winner_of(cells)
        if w or not empty_cells(cells):
            return w
        turn = other(turn)


class AITests(unittest.TestCase):
    def test_takes_winning_move(self):
        cells = [X, X, "", O, O, "", "", "", ""]
        self.assertEqual(best_move(cells, X), 2)
        self.assertEqual(best_move(cells, O), 5)

    def test_blocks_opponent(self):
        cells = [X, X, "", "", O, "", "", "", ""]
        self.assertEqual(best_move(cells, O), 2)

    def test_medium_wins_and_blocks_when_not_blundering(self):
        class NoBlunder(random.Random):
            def random(self):
                return 0.99
        cells = [X, X, "", "", O, "", "", "", ""]
        self.assertEqual(choose_move(cells, O, "medium", NoBlunder()), 2)      # block
        cells = [O, O, "", X, X, "", "", "", ""]
        self.assertEqual(choose_move(cells, O, "medium", NoBlunder()), 2)      # win beats block

    def test_always_returns_a_free_cell(self):
        cells = [X, O, X, O, X, O, "", "", ""]
        for lvl in ("easy", "medium", "hard"):
            for seed in range(20):
                self.assertIn(choose_move(cells, O, lvl, random.Random(seed)), (6, 7, 8))

    def test_full_board_returns_none(self):
        cells = [X, O, X, X, O, O, O, X, X]
        self.assertIsNone(choose_move(cells, X, "hard"))

    def test_hard_never_loses(self):
        for opponent in ("easy", "medium", "hard"):
            for seed in range(15):
                self.assertNotEqual(play("hard", opponent, seed), O)      # hard = X
                self.assertNotEqual(play(opponent, "hard", seed), X)      # hard = O

    def test_hard_vs_hard_is_a_draw(self):
        for seed in range(10):
            self.assertIsNone(play("hard", "hard", seed))


if __name__ == "__main__":
    unittest.main()
