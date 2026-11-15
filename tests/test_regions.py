import unittest

from minitel import M1, Registry, Region, Screen, Session, page
from minitel.protocol import codec

from pages.common.widgets import line_field

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])
BEL = bytes([codec.BEL])


def _pane_render(ctx):
    query = ctx.state.get("query")
    ctx.set_regions(
        Region("form", next="results"),
        Region("results", prev="form", activate="stay", key=query),
    )
    screen = Screen()
    screen.text(1, 0, "PANE")
    line_field(screen, ctx, "origin", 2, 2, 3, label="A:", region="form")
    line_field(
        screen, ctx, "destination", 2, 10, 3, label="B:", region="form"
    )
    pager = ctx.set_pager(5, 2, region="results")
    for index, item in enumerate(pager.window(tuple(range(5)))):
        screen.text(5 + index, 0, f"ITEM {item}")
    screen.text(8, 0, pager.label)
    screen.text(10, 0, f"FOCUS {ctx.focused_region}")
    return screen


def _pane_submit(ctx, values):
    origin = values.get("origin", "").strip().upper()
    destination = values.get("destination", "").strip().upper()
    if len(origin) != 3:
        ctx.focus("origin")
        return "960"
    ctx.state["query"] = (origin, destination)
    ctx.state["submits"] = ctx.state.get("submits", 0) + 1
    ctx.focus_region("results")
    return "960"


@page("959")
def home(ctx):
    screen = Screen()
    screen.text(0, 0, "HOME")
    return screen


@page(
    "960",
    form=True,
    on_form=_pane_submit,
    on_tick=_pane_render,
    tick_interval=1.0,
)
def pane(ctx):
    return _pane_render(ctx)


def _bad_tick(ctx):
    ctx.set_regions(
        Region("form", next="results"),
        Region("results", prev="form", key="changed"),
    )
    ctx.add_field("origin", 2, 2, 3, region="form")
    ctx.set_pager(5, 2, region="results")
    return None


def _bad_render(ctx):
    ctx.set_regions(
        Region("form", next="results"),
        Region("results", prev="form", key="initial"),
    )
    screen = Screen()
    ctx.add_field("origin", 2, 2, 3, region="form")
    ctx.set_pager(5, 2, region="results")
    return screen


@page(
    "961",
    form=True,
    on_tick=_bad_tick,
    tick_interval=1.0,
)
def bad_tick(ctx):
    return _bad_render(ctx)


@page("968")
def implicit_pager(ctx):
    screen = Screen()
    pager = ctx.set_pager(4, 2)
    screen.text(0, 0, f"P{pager.page_number}")
    return screen


def make_session(*pages, initial="959"):
    registry = Registry()
    for page_object in pages:
        registry.add(page_object)
    session = Session(
        registry,
        M1,
        initial=initial,
        fallback=registry.get(initial),
    )
    session.start()
    return session


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session(home, pane)
        self.session.navigate("960")

    def test_form_is_the_initial_region(self):
        self.assertEqual(self.session.focused_region, "form")
        self.assertEqual(self.session.regions["form"].fields[0].name, "origin")
        self.assertTrue(self.session.screen.cursor_visible)
        self.assertIn("FOCUS form", self.session.screen.to_text())

    def test_enter_submits_and_focuses_results(self):
        self.session.feed(b"PAD" + ENVOI)
        self.assertEqual(self.session.focused_region, "results")
        self.assertEqual(self.session.state["query"], ("PAD", ""))
        self.assertEqual(self.session.state["submits"], 1)
        self.assertEqual(
            self.session.regions["results"].cursor.page_number, 1
        )
        self.assertFalse(self.session.screen.cursor_visible)
        self.assertIn("ITEM 0", self.session.screen.to_text())

    def test_pager_pages_and_retour_returns_to_the_form(self):
        self.session.feed(b"PAD" + ENVOI)
        self.session.feed(SUITE)
        self.assertEqual(
            self.session.regions["results"].cursor.page_number, 2
        )
        self.session.feed(RETOUR)
        self.assertEqual(
            self.session.regions["results"].cursor.page_number, 1
        )
        self.assertEqual(self.session.focused_region, "results")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.focused_region, "form")

    def test_root_retour_uses_history(self):
        self.session.feed(b"PAD" + ENVOI)
        self.session.feed(RETOUR)  # first results page -> form
        self.session.feed(RETOUR)  # first form field -> history
        self.assertEqual(self.session.current.number, "959")
        self.assertEqual(self.session.regions, {})

    def test_focus_and_pager_are_remembered_on_return(self):
        self.session.feed(b"PAD" + ENVOI)
        self.session.feed(SUITE)
        self.session.navigate("959")
        self.session.navigate("960")
        self.assertEqual(self.session.focused_region, "results")
        self.assertEqual(
            self.session.regions["results"].cursor.page_number, 2
        )

    def test_new_query_resets_the_pager(self):
        self.session.feed(b"PAD" + ENVOI)
        self.session.feed(SUITE)
        self.session.feed(RETOUR)
        self.session.feed(RETOUR)
        self.assertEqual(self.session.focused_region, "form")
        self.session.values["origin"] = "KGX"
        self.session.feed(ENVOI)
        self.assertEqual(self.session.state["query"], ("KGX", ""))
        self.assertEqual(
            self.session.regions["results"].cursor.page_number, 1
        )

    def test_results_enter_refreshes_without_resubmitting(self):
        self.session.feed(b"PAD" + ENVOI)
        self.session.feed(ENVOI)
        self.assertEqual(self.session.state["submits"], 1)
        self.assertEqual(self.session.focused_region, "results")

    def test_text_is_ignored_outside_the_form(self):
        self.session.feed(b"PAD" + ENVOI)
        actions = self.session.feed(b"X")
        self.assertEqual(actions[0].raw, BEL)
        self.assertEqual(self.session.values["origin"], "PAD")

    def test_tick_keeps_focus_and_pager(self):
        self.session.feed(b"PAD" + ENVOI)
        self.session.feed(SUITE)
        action = self.session.tick()
        self.assertIsNone(self.session.page_error)
        self.assertEqual(self.session.focused_region, "results")
        self.assertEqual(
            self.session.regions["results"].cursor.page_number, 2
        )

    def test_implicit_pager_still_wraps(self):
        session = make_session(home, implicit_pager)
        session.navigate("968")
        session.feed(SUITE)
        self.assertEqual(session.pager.page_number, 2)
        session.feed(SUITE)
        self.assertEqual(session.pager.page_number, 1)

    def test_tick_cannot_change_regions(self):
        session = make_session(home, bad_tick)
        session.navigate("961")
        action = session.tick()
        self.assertIn("PAGE ERROR", action.screen.to_text())
        self.assertEqual(session.page_error, "tick")
        self.assertIn("961", session._ticks_disabled)


class RegionValidationTests(unittest.TestCase):
    def _start(self, page_object):
        session = make_session(home, page_object)
        session.navigate(page_object.number)

    def test_duplicate_region_names(self):
        @page("962")
        def bad(ctx):
            ctx.set_regions(Region("a"), Region("a"))
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_unknown_edge(self):
        @page("963")
        def bad(ctx):
            ctx.set_regions(Region("a", next="missing"))
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_default_focus_must_exist(self):
        @page("964")
        def bad(ctx):
            ctx.set_regions(Region("a"), default_focus="missing")
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_named_page_requires_explicit_pager_region(self):
        @page("965")
        def bad(ctx):
            ctx.set_regions(Region("form", next="results"),
                            Region("results", prev="form"))
            ctx.set_pager(3, 2)
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_each_region_needs_a_cursor(self):
        @page("969", form=True)
        def bad(ctx):
            ctx.set_regions(
                Region("form", next="results"),
                Region("results", prev="form"),
            )
            ctx.add_field("origin", 2, 2, 3, region="form")
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_named_form_requires_form_true(self):
        @page("966")
        def bad(ctx):
            ctx.set_regions(Region("form"))
            ctx.add_field("origin", 2, 2, 3, region="form")
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_named_choice_is_not_enabled(self):
        @page("967")
        def bad(ctx):
            ctx.set_regions(Region("results"))
            ctx.set_choice(3, 2)
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_region_value_validation(self):
        with self.assertRaises(ValueError):
            Region("main")
        with self.assertRaises(ValueError):
            Region("a", next="a")
        with self.assertRaises(ValueError):
            Region("a", activate="focus:b")
        with self.assertRaises(TypeError):
            Region("a", key=[])


if __name__ == "__main__":
    unittest.main()
