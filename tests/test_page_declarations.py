import unittest

from minitel import Registry, Screen, Session, page
from minitel.design.field import InputField
from minitel.terminal.profiles import M1


def make_session(page_object):
    registry = Registry()
    registry.add(page_object)
    return Session(
        registry,
        M1,
        initial=page_object.number,
        fallback=page_object,
    )


class PageDeclarationTests(unittest.TestCase):
    def test_page_rejects_unknown_keywords(self):
        with self.assertRaises(TypeError):
            page("960", titel="TYPO")(lambda ctx: Screen())

    def test_page_meta_is_explicit(self):
        @page("961", meta={"kind": "demo"})
        def demo(ctx):
            return Screen()

        self.assertEqual(demo.meta, {"kind": "demo"})

    def test_page_records_its_defining_module(self):
        @page("962")
        def demo(ctx):
            return Screen()

        self.assertEqual(demo.defined_in, __name__)

    def test_mask_is_not_part_of_the_field_api(self):
        with self.assertRaises(TypeError):
            InputField("name", 0, 0, 4, mask="AAAA")

        @page("963")
        def bad(ctx):
            ctx.add_field("name", 0, 0, 4, mask="AAAA")
            return Screen()

        with self.assertRaises(TypeError):
            make_session(bad).start()

    def test_field_geometry_is_validated(self):
        cases = (
            (-1, 0, 1),
            (25, 0, 1),
            (0, -1, 1),
            (0, 40, 1),
            (0, 0, 0),
            (0, 39, 2),
        )
        for index, (row, col, width) in enumerate(cases):
            @page(str(970 + index))
            def bad(ctx, row=row, col=col, width=width):
                ctx.set_input(row, col, width)
                return Screen()

            with self.subTest(row=row, col=col, width=width):
                with self.assertRaises(ValueError):
                    make_session(bad).start()

    def test_field_at_the_edges_is_valid(self):
        @page("978")
        def edge(ctx):
            ctx.set_input(24, 19, 21)
            return Screen()

        screen = make_session(edge).start()
        self.assertIsInstance(screen, Screen)

    def test_form_fields_and_a_choice_are_rejected_in_both_orders(self):
        @page("979", form=True)
        def fields_first(ctx):
            ctx.set_input(1, 0, 5)
            ctx.set_choice(4, 2)
            return Screen()

        @page("980", form=True)
        def choice_first(ctx):
            ctx.set_choice(4, 2)
            ctx.set_input(1, 0, 5)
            return Screen()

        for bad in (fields_first, choice_first):
            with self.subTest(page=bad.number):
                with self.assertRaises(ValueError):
                    make_session(bad).start()

    def test_screen_clear_keeps_presentation_hints(self):
        screen = Screen()
        screen.put(0, 0, "X")
        screen.paint = "cell"
        screen.paint_order = "up"
        screen.force_full = True
        screen.set_cursor(4, 5, False)

        screen.clear()

        self.assertEqual(screen.rows[0][0].ch, " ")
        self.assertEqual((screen.cursor_row, screen.cursor_col), (1, 0))
        self.assertTrue(screen.cursor_visible)
        self.assertEqual(screen.paint, "cell")
        self.assertEqual(screen.paint_order, "up")
        self.assertTrue(screen.force_full)


if __name__ == "__main__":
    unittest.main()
