import unittest

from src.board import Board
from src.config import X, O
from src.game_rules import evaluate, WIN_LINES, WIN, DRAW, PLAYING
from src.game_state import Game, MoveResult, State
from src.config import Config
from src.turn_manager import TurnManager, make_players


def board_with(cells):
    b = Board()
    for i, s in cells.items():
        b.place(i, s)
    return b


class RulesTests(unittest.TestCase):
    def test_all_eight_lines_win(self):                          # Rows / Columns / Diagonals
        self.assertEqual(len(WIN_LINES), 8)
        for line in WIN_LINES:
            for sym in (X, O):
                out = evaluate(board_with({i: sym for i in line}))
                self.assertEqual((out.status, out.symbol, out.line), (WIN, sym, line))

    def test_draw(self):                                         # Draw Test
        # X O X / X O O / O X X  -> no line
        cells = dict(enumerate([X, O, X, X, O, O, O, X, X]))
        self.assertEqual(evaluate(board_with(cells)).status, DRAW)

    def test_game_continues(self):
        self.assertEqual(evaluate(board_with({0: X, 4: O})).status, PLAYING)


class TurnAndGameTests(unittest.TestCase):
    def setUp(self):
        self.g = Game(Config())
        self.g.start_match()
        self.g.start_round()

    def test_turn_switches_only_after_valid_move(self):          # Turn Test
        self.assertEqual(self.g.turns.current.symbol, X)
        self.assertEqual(self.g.try_place(0, 1.0), MoveResult.PLACED)
        self.assertEqual(self.g.turns.current.symbol, O)
        self.assertEqual(self.g.try_place(0, 2.0), MoveResult.OCCUPIED)   # invalid
        self.assertEqual(self.g.turns.current.symbol, O)                  # still O's turn
        self.assertEqual(self.g.board.get(0), X)

    def test_win_updates_score_and_stops_play(self):
        for cell in (0, 3, 1, 4, 2):
            self.g.try_place(cell, 1.0)
        self.assertEqual(self.g.state, State.ROUND_RESULT)
        self.assertEqual(self.g.scores.wins, [1, 0])
        self.assertEqual(self.g.try_place(8, 2.0), MoveResult.IGNORED)    # no play after a win

    def test_draw_does_not_change_scores(self):
        for cell in (0, 1, 2, 4, 3, 5, 7, 6, 8):                           # X O X / O X O / O X ... draw
            res = self.g.try_place(cell, 1.0)
        self.assertEqual(res, MoveResult.DRAW)
        self.assertEqual(self.g.scores.wins, [0, 0])
        self.assertEqual(self.g.scores.draws, 1)

    def test_new_round_clears_board_keeps_score_alternates_starter(self):
        for cell in (0, 3, 1, 4, 2):
            self.g.try_place(cell, 1.0)
        self.g.new_round()
        self.assertEqual(self.g.board.empty_cells(), list(range(9)))
        self.assertEqual(self.g.scores.wins, [1, 0])
        self.assertEqual(self.g.turns.current.symbol, O)                   # starter alternated

    def test_turn_manager_first_player(self):
        tm = TurnManager(make_players(["A", "B"]), first=1)
        self.assertEqual(tm.current.symbol, O)


if __name__ == "__main__":
    unittest.main()
