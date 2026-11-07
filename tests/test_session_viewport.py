import unittest

from minitel.pagemodel import Registry, page
from minitel.render import Screen
from minitel.session import Session
from minitel.terminal.profiles import M1

RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])
UP = b"\x1b[A"
DOWN = b"\x1b[B"

LINES = tuple(f"L{n:02d}" for n in range(40))


def make_static_page(number="560", *, follow=False, back_page="570", step=1):
    @page(number, scroll=True, back_page=back_page)
    def paged(ctx):
        default_follow = follow if ctx.viewport is None else None
        total = ctx.state.get("total", 12)
        view = ctx.set_viewport(total, 5, follow=default_follow, step=step)
        screen = Screen()
        for index, line in enumerate(view.window(LINES)):
            screen.text(1 + index, 0, line)
        return screen

    return paged


def make_dynamic_page(number="560", *, follow=True, back_page="570"):
    def render(ctx):
        total = ctx.state.get("total", 12)
        default_follow = follow if ctx.viewport is None else None
        view = ctx.set_viewport(total, 5, follow=default_follow)
        screen = Screen()
        for index, line in enumerate(view.window(LINES)):
            screen.text(1 + index, 0, line)
        return screen

    def tick(ctx):
        ctx.state["total"] = ctx.state.get("total", 12) + 1
        return render(ctx)

    return page(
        number,
        scroll=True,
        back_page=back_page,
        tick_interval=1.0,
        on_tick=tick,
    )(render)


class SessionViewportTests(unittest.TestCase):
    def make_session(self, page_object, other=None):
        registry = Registry()
        registry.add(page_object)
        if other is not None:
            registry.add(other)
        session = Session(registry, M1, initial=page_object.number, fallback=page_object)
        session.start()
        return session

    def test_starts_at_top_and_steps_one_line(self):
        session = self.make_session(make_static_page())
        self.assertEqual(session.viewport.offset, 0)

        session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 1)
        self.assertFalse(session.viewport.follow)

        session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 2)

        session.feed(RETOUR)
        self.assertEqual(session.viewport.offset, 1)

        session.feed(RETOUR)
        self.assertEqual(session.viewport.offset, 0)

    def test_per_viewport_step(self):
        session = self.make_session(make_static_page(step=5))
        session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 5)

        session.feed(DOWN)
        self.assertEqual(session.viewport.offset, 6)
        session.feed(UP)
        self.assertEqual(session.viewport.offset, 5)

        session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 7)
        self.assertTrue(session.viewport.follow)

        session.feed(RETOUR)
        self.assertEqual(session.viewport.offset, 2)

    def test_arrows_move_one_line(self):
        session = self.make_session(make_static_page())
        session.feed(DOWN)
        self.assertEqual(session.viewport.offset, 1)
        session.feed(UP)
        self.assertEqual(session.viewport.offset, 0)
        session.feed(UP)
        self.assertEqual(session.viewport.offset, 0)

    def test_retour_at_top_uses_back_page(self):
        other = page("570")(lambda ctx: Screen())
        session = self.make_session(make_static_page(), other)
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "570")

    def test_remembers_position_per_page(self):
        other = page("570")(lambda ctx: Screen())
        session = self.make_session(make_static_page(), other)
        session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 1)

        session.navigate("570")
        session.navigate("560")
        self.assertEqual(session.viewport.offset, 1)

    def test_follow_tail_freezes_and_resumes(self):
        session = self.make_session(make_dynamic_page())
        self.assertEqual(session.viewport.offset, 7)
        self.assertTrue(session.viewport.follow)

        session.tick()
        self.assertEqual(session.viewport.offset, 8)
        self.assertTrue(session.viewport.follow)

        session.feed(UP)
        self.assertEqual(session.viewport.offset, 7)
        self.assertFalse(session.viewport.follow)

        session.tick()
        self.assertEqual(session.viewport.offset, 7)
        self.assertFalse(session.viewport.follow)

        session.feed(SUITE)
        session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 9)
        self.assertTrue(session.viewport.follow)

    def test_content_shrink_clamps_offset(self):
        session = self.make_session(make_static_page())
        for _ in range(7):
            session.feed(SUITE)
        self.assertEqual(session.viewport.offset, 7)

        session.state["total"] = 3
        session.refresh()
        self.assertEqual(session.viewport.total, 3)
        self.assertEqual(session.viewport.offset, 0)

    def test_ctx_viewport_is_active_cursor(self):
        seen = []

        @page("580", scroll=True)
        def paged(ctx):
            seen.append(ctx.viewport)
            ctx.set_viewport(4, 2)
            return Screen()

        session = self.make_session(paged)
        self.assertIsNone(seen[0])
        session.feed(SUITE)
        self.assertIsNotNone(seen[1])

    def test_viewport_requires_scroll_page(self):
        @page("581")
        def bad(ctx):
            ctx.set_viewport(4, 2)
            return Screen()

        with self.assertRaises(ValueError):
            self.make_session(bad)

    def test_viewport_and_pager_conflict(self):
        @page("582", scroll=True)
        def bad(ctx):
            ctx.set_pager(4, 2)
            ctx.set_viewport(4, 2)
            return Screen()

        with self.assertRaises(ValueError):
            self.make_session(bad)

        @page("583", scroll=True)
        def bad_reverse(ctx):
            ctx.set_viewport(4, 2)
            ctx.set_pager(4, 2)
            return Screen()

        with self.assertRaises(ValueError):
            self.make_session(bad_reverse)

    def test_form_and_viewport_conflict(self):
        @page("584", form=True, scroll=True)
        def bad(ctx):
            ctx.set_input(1, 0, 5)
            ctx.set_viewport(4, 2)
            return Screen()

        with self.assertRaises(ValueError):
            self.make_session(bad)

    def test_single_input_plus_viewport_is_allowed(self):
        @page("585", scroll=True)
        def allowed(ctx):
            ctx.set_input(1, 0, 5)
            ctx.set_viewport(4, 2)
            return Screen()

        session = self.make_session(allowed)
        self.assertIsNotNone(session.viewport)
        self.assertEqual(len(session.fields), 1)


if __name__ == "__main__":
    unittest.main()
