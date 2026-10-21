import unittest

from src.board import Board
from src.config import X, O, EMPTY


class BoardTests(unittest.TestCase):
    def test_starts_empty(self):
        self.assertEqual(Board().flat(), [EMPTY] * 9)

    def test_place_and_read(self):
        b = Board()
        self.assertTrue(b.place(4, X))
        self.assertEqual(b.get(4), X)
        self.assertEqual(b.grid[1][1], X)

    def test_occupied_cell_cannot_be_overwritten(self):          # Invalid Move Test
        b = Board()
        b.place(0, X)
        self.assertFalse(b.place(0, O))
        self.assertEqual(b.get(0), X)

    def test_out_of_range_and_bad_symbol(self):
        b = Board()
        self.assertFalse(b.place(9, X))
        self.assertFalse(b.place(-1, X))
        self.assertFalse(b.place(0, "Z"))
        self.assertEqual(b.flat(), [EMPTY] * 9)

    def test_full_and_reset(self):                               # Reset Test
        b = Board()
        for i in range(9):
            b.place(i, X if i % 2 else O)
        self.assertTrue(b.is_full())
        b.reset()
        self.assertEqual(len(b.empty_cells()), 9)


if __name__ == "__main__":
    unittest.main()
