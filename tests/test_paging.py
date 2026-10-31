import unittest

from minitel.paging import Pager


class PagerTests(unittest.TestCase):
    def test_first_page(self):
        pager = Pager(12, 5)
        self.assertEqual(pager.page_count, 3)
        self.assertEqual(pager.page_number, 1)
        self.assertEqual(pager.label, "1/3")
        self.assertEqual(pager.window(range(12)), (0, 1, 2, 3, 4))

    def test_middle_page(self):
        pager = Pager(12, 5, 5)
        self.assertEqual(pager.page_number, 2)
        self.assertEqual(pager.window(range(12)), (5, 6, 7, 8, 9))

    def test_partial_last_page(self):
        pager = Pager(12, 5, 10)
        self.assertEqual(pager.label, "3/3")
        self.assertEqual(pager.window(range(12)), (10, 11))

    def test_clamp(self):
        self.assertEqual(Pager(12, 5, 99).clamp().offset, 10)
        self.assertEqual(Pager(12, 5, -3).clamp().offset, 0)

    def test_next(self):
        self.assertEqual(Pager(12, 5).next().offset, 5)
        self.assertEqual(Pager(12, 5, 10).next().offset, 10)
        self.assertEqual(Pager(12, 5, 10).next(wrap=True).offset, 0)

    def test_prev(self):
        self.assertEqual(Pager(12, 5, 5).prev().offset, 0)
        self.assertEqual(Pager(12, 5).prev().offset, 0)
        self.assertEqual(Pager(12, 5).prev(wrap=True).offset, 10)

    def test_empty(self):
        pager = Pager(0, 5)
        self.assertEqual(pager.page_count, 0)
        self.assertEqual(pager.label, "0/0")
        self.assertEqual(pager.window([]), ())
        self.assertEqual(pager.next().offset, 0)
        self.assertEqual(pager.prev().offset, 0)

    def test_invalid_page_size(self):
        with self.assertRaises(ValueError):
            Pager(10, 0)


if __name__ == "__main__":
    unittest.main()
