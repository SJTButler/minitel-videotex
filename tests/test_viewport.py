import unittest

from minitel.design import Viewport


class ViewportTests(unittest.TestCase):
    def test_empty(self):
        view = Viewport(0, 5)
        self.assertEqual(view.max_offset, 0)
        self.assertTrue(view.at_top)
        self.assertTrue(view.at_bottom)
        self.assertEqual(view.line_number, 0)
        self.assertEqual(view.window([]), ())

    def test_short_content(self):
        lines = ("one", "two", "three")
        view = Viewport(3, 5)
        self.assertEqual(view.max_offset, 0)
        self.assertEqual(view.window(lines), lines)
        self.assertTrue(view.at_top)
        self.assertTrue(view.at_bottom)

    def test_clamp(self):
        self.assertEqual(Viewport(12, 5, 99).clamp().offset, 7)
        self.assertEqual(Viewport(12, 5, -3).clamp().offset, 0)

    def test_window(self):
        lines = tuple(str(n) for n in range(12))
        view = Viewport(12, 5, 3)
        self.assertEqual(view.window(lines), ("3", "4", "5", "6", "7"))
        self.assertEqual(view.line_number, 4)

    def test_line_movement(self):
        view = Viewport(12, 5, 0)
        self.assertEqual(view.line_down().offset, 1)
        self.assertEqual(Viewport(12, 5, 1).line_up().offset, 0)
        self.assertEqual(Viewport(12, 5, 7).line_down().offset, 7)
        self.assertEqual(Viewport(12, 5, 0).line_up().offset, 0)

    def test_line_movement_freezes_follow(self):
        view = Viewport(12, 5, 7, follow=True)
        self.assertFalse(view.line_up().follow)
        at_tail = Viewport(12, 5, 7, follow=True)
        self.assertTrue(at_tail.line_down().follow)

    def test_step_movement(self):
        view = Viewport(12, 5, 0, step=4)
        self.assertEqual(view.step_down().offset, 4)
        self.assertEqual(Viewport(12, 5, 4, step=4).step_up().offset, 0)
        self.assertEqual(Viewport(12, 5, 7, step=4).step_down().offset, 7)
        self.assertTrue(Viewport(12, 5, 7, step=4).step_down().follow)

    def test_arrow_movement_ignores_step(self):
        view = Viewport(12, 5, 0, step=4)
        self.assertEqual(view.line_down().offset, 1)
        self.assertEqual(Viewport(12, 5, 1, step=4).line_up().offset, 0)

    def test_step_is_preserved(self):
        self.assertEqual(Viewport(12, 5, 3, step=4).clamp().step, 4)
        self.assertEqual(Viewport(12, 5, 3, step=4).tail().step, 4)
        self.assertEqual(Viewport(12, 5, 3, step=4).with_total(20).step, 4)

    def test_line_down_at_tail_resumes_follow(self):
        view = Viewport(12, 5, 7, follow=False)
        self.assertEqual(view.line_down().offset, 7)
        self.assertTrue(view.line_down().follow)

    def test_invalid_step(self):
        with self.assertRaises(ValueError):
            Viewport(10, 5, step=0)

    def test_page_movement(self):
        view = Viewport(12, 5, 0)
        self.assertEqual(view.page_down().offset, 5)
        self.assertEqual(Viewport(12, 5, 5).page_down().offset, 7)
        self.assertEqual(Viewport(12, 5, 7).page_up().offset, 2)

    def test_page_movement_with_overlap(self):
        view = Viewport(12, 5, 0)
        self.assertEqual(view.page_down(overlap=1).offset, 4)
        self.assertEqual(Viewport(12, 5, 4).page_down(overlap=1).offset, 7)
        self.assertEqual(Viewport(12, 5, 7).page_up(overlap=1).offset, 3)

    def test_page_down_at_tail_resumes_follow(self):
        view = Viewport(12, 5, 7, follow=False)
        moved = view.page_down(overlap=1)
        self.assertEqual(moved.offset, 7)
        self.assertTrue(moved.follow)

    def test_tail(self):
        view = Viewport(12, 5).tail()
        self.assertEqual(view.offset, 7)
        self.assertTrue(view.follow)

    def test_with_total(self):
        following = Viewport(10, 4, 6, follow=True).with_total(20)
        self.assertEqual(following.offset, 16)
        self.assertTrue(following.follow)

        frozen = Viewport(20, 4, 10, follow=False).with_total(5)
        self.assertEqual(frozen.offset, 1)
        self.assertFalse(frozen.follow)

    def test_invalid_height(self):
        with self.assertRaises(ValueError):
            Viewport(10, 0)

    def test_invalid_total(self):
        with self.assertRaises(ValueError):
            Viewport(-1, 5)


if __name__ == "__main__":
    unittest.main()
