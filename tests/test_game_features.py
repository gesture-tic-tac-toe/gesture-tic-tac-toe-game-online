import unittest

from src.config import Config, X, O
from src.game_state import Game, MoveResult, State


def new_game(**kw):
    cfg = Config()
    for k, v in kw.items():
        setattr(cfg, k, v)
    g = Game(cfg)
    g.start_match()
    g.start_round()
    return g


def x_wins_top_row(g, now=1.0):
    for cell in (0, 3, 1, 4, 2):
        res = g.try_place(cell, now)
    return res


class MatchTests(unittest.TestCase):
    def test_match_won_at_target(self):
        g = new_game(match_target=2, alternate_first=False)
        self.assertEqual(x_wins_top_row(g), MoveResult.WIN)
        self.assertIsNone(g.match_winner)
        g.new_round()
        x_wins_top_row(g)
        self.assertEqual(g.match_winner, 0)
        self.assertIn("Player 1", g.result_text())

    def test_endless_match_never_ends(self):
        g = new_game(match_target=0, alternate_first=False)
        for _ in range(4):
            x_wins_top_row(g)
            g.new_round()
        self.assertIsNone(g.match_winner)
        self.assertEqual(g.scores.wins[0], 4)

    def test_rematch_resets_score(self):
        g = new_game(match_target=1)
        x_wins_top_row(g)
        self.assertEqual(g.match_winner, 0)
        g.new_round()                                   # = rematch
        self.assertIsNone(g.match_winner)
        self.assertEqual(g.scores.wins, [0, 0])
        self.assertEqual(g.state, State.PLAYING)

    def test_stats_recorded(self):
        g = new_game(match_target=1)
        x_wins_top_row(g)
        self.assertEqual(g.stats.data["pvp"]["p1"], 1)


class PauseCountdownTests(unittest.TestCase):
    def test_pause_blocks_moves_and_resume_restores(self):
        g = new_game()
        self.assertTrue(g.pause())
        self.assertEqual(g.state, State.PAUSED)
        self.assertEqual(g.try_place(0, 1.0), MoveResult.IGNORED)
        g.resume()
        self.assertEqual(g.try_place(0, 1.0), MoveResult.PLACED)

    def test_cannot_pause_outside_play(self):
        g = Game(Config())
        self.assertFalse(g.pause())

    def test_countdown_sequence(self):
        g = new_game(countdown=True)
        self.assertEqual(g.countdown_label(10.0)[0], "3")
        self.assertEqual(g.countdown_label(10.9)[0], "2")
        self.assertEqual(g.countdown_label(11.7)[0], "1")
        self.assertGreater(g.countdown_left(11.7), 0)
        self.assertEqual(g.countdown_label(12.5)[0], "GO!")
        self.assertEqual(g.countdown_left(12.5), 0)
        self.assertEqual(g.countdown_label(13.5)[0], "")

    def test_countdown_can_be_disabled(self):
        g = new_game(countdown=False)
        self.assertEqual(g.countdown_left(10.0), 0.0)
        self.assertEqual(g.countdown_label(10.0)[0], "")


class TimerTests(unittest.TestCase):
    def test_timer_off_by_default(self):
        g = new_game()
        self.assertIsNone(g.turn_time_left(5.0))

    def test_timeout_plays_random_move_and_switches_turn(self):
        g = new_game(turn_timer=10)
        self.assertEqual(g.turn_time_left(100.0), 10)
        self.assertAlmostEqual(g.turn_time_left(104.0), 6)
        self.assertIsNone(g.tick(105.0))
        res = g.tick(110.5)
        self.assertEqual(res, MoveResult.PLACED)
        self.assertEqual(g.board.flat().count(X), 1)
        self.assertEqual(g.turns.current.symbol, O)
        self.assertEqual(g.turn_time_left(111.0), 10)          # fresh clock for the next turn


class AIGameTests(unittest.TestCase):
    def test_computer_plays_after_delay(self):
        g = new_game(mode="ai", ai_level="hard")
        self.assertEqual(g.players[1].name, "Computer")
        g.try_place(0, 1.0)
        self.assertTrue(g.is_ai_turn())
        self.assertIsNone(g.tick(2.0))                         # "thinking"
        res = g.tick(2.0 + g.AI_DELAY[1] + 0.01)
        self.assertEqual(res, MoveResult.PLACED)
        self.assertEqual(g.board.flat().count(O), 1)
        self.assertFalse(g.is_ai_turn())                       # back to the human

    def test_computer_never_moves_when_paused(self):
        g = new_game(mode="ai")
        g.try_place(0, 1.0)
        g.pause()
        self.assertIsNone(g.tick(99.0))
        self.assertEqual(g.board.flat().count(O), 0)

    def test_full_game_vs_hard_computer_human_never_wins_by_random_play(self):
        import random
        rng = random.Random(3)
        for _ in range(30):
            g = new_game(mode="ai", ai_level="hard", match_target=0)
            now = 1.0
            while g.state is State.PLAYING:
                now += 2.0
                if g.is_ai_turn():
                    g.tick(now)
                    g.tick(now + 1.5)
                else:
                    g.try_place(rng.choice(g.board.empty_cells()), now)
            self.assertEqual(g.scores.wins[0], 0)              # human (X) never beats hard AI

    def test_computer_names_follow_mode(self):
        g = new_game(mode="pvp")
        g.sync_names()
        self.assertEqual(g.players[1].name, "Player 2")


class HintTests(unittest.TestCase):
    def test_hint_finds_winning_cell(self):
        g = new_game()
        for cell in (0, 3, 1, 4):                              # X can win at 2
            g.try_place(cell, 1.0)
        self.assertEqual(g.show_hint(5.0), 2)
        self.assertEqual(g.hint_cell, 2)

    def test_hint_cleared_after_move(self):
        g = new_game()
        g.show_hint(5.0)
        g.try_place(4, 5.5)
        self.assertIsNone(g.hint_cell)

    def test_no_hint_on_computer_turn(self):
        g = new_game(mode="ai")
        g.try_place(0, 1.0)
        self.assertIsNone(g.show_hint(2.0))


if __name__ == "__main__":
    unittest.main()
