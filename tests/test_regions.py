import unittest

from minitel import M1, PAGE_BACK, Registry, Region, Screen, Session, page
from minitel.protocol import codec

from pages.common.widgets import line_field

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])
ANNULATION = bytes([0x13, 0x45])
CORRECTION = bytes([0x13, 0x47])
BEL = bytes([codec.BEL])


def _pane_render(ctx):
    query = ctx.state.get("query")
    screen = Screen()
    screen.text(1, 0, "PANE")
    line_field(screen, ctx, "origin", 2, 2, 3, label="A:", region="form")
    line_field(
        screen, ctx, "destination", 2, 10, 3, label="B:", region="form"
    )
    pager = ctx.set_pager(5, region="results", key=query)
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
    regions=(
        Region("form", kind="form", next="results"),
        Region(
            "results",
            kind="pager",
            prev="form",
            activate="stay",
            page_size=2,
        ),
    ),
)
def pane(ctx):
    return _pane_render(ctx)


@page("968")
def implicit_pager(ctx):
    screen = Screen()
    pager = ctx.set_pager(4, 2)
    screen.text(0, 0, f"P{pager.page_number}")
    return screen


@page(
    "970",
    regions=(Region("choices", kind="choice", page_size=2),),
)
def choice_region(ctx):
    choice = ctx.set_choice(3, region="choices")
    screen = Screen()
    screen.text(0, 0, f"SEL {choice.selected}")
    return screen


def _choice_submit(ctx, line):
    ctx.state["committed"] = ctx.region("choices").committed
    return "971"


def _choice_back(ctx):
    ctx.state["back"] = True
    return True


@page(
    "971",
    on_submit=_choice_submit,
    on_back=_choice_back,
    regions=(
        Region(
            "choices",
            kind="choice",
            prev=PAGE_BACK,
            page_size=2,
        ),
    ),
)
def choice_commit(ctx):
    choice = ctx.set_choice(
        3,
        region="choices",
        commit=lambda cursor: cursor.selected,
    )
    screen = Screen()
    screen.text(0, 0, f"SEL {choice.selected}")
    return screen


@page("975", regions=(Region("items", kind="choice", page_size=2),))
def choice_remove(ctx):
    items = ctx.state.setdefault("items", ["A", "B", "C"])
    ctx.set_choice(
        items,
        region="items",
        key="items",
        remove=lambda item: items.remove(item),
    )
    screen = Screen()
    screen.text(0, 0, " ".join(items))
    return screen


@page("976", regions=(Region("items", kind="choice", page_size=2),))
def choice_no_remove(ctx):
    ctx.set_choice(("A", "B", "C"), region="items", key="items")
    screen = Screen()
    screen.text(0, 0, "NO REMOVE")
    return screen


@page("977", regions=(Region("items", kind="choice", page_size=2),))
def choice_commands(ctx):
    ctx.set_choice(
        ("A", "B", "C"),
        region="items",
        key="items",
        commands={
            "*": lambda item: ctx.state.__setitem__("moved", item),
        },
    )
    screen = Screen()
    screen.text(0, 0, f"MOVED {ctx.state.get('moved', 'NONE')}")
    return screen


def _correct_key(ctx, name):
    if name == "CORRECTION":
        ctx.state["corrected"] = True
    return None


@page(
    "978",
    on_key=_correct_key,
    regions=(Region("items", kind="choice", page_size=2),),
)
def choice_correct(ctx):
    ctx.set_choice(("A", "B", "C"), region="items", key="items")
    screen = Screen()
    screen.text(
        0, 0, "CORRECT" if ctx.state.get("corrected") else "PLAIN"
    )
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

    def test_named_choice_moves_selection(self):
        session = make_session(home, choice_region)
        session.navigate("970")
        self.assertEqual(session.regions["choices"].cursor.selected, 0)

        session.feed(SUITE)
        self.assertEqual(session.regions["choices"].cursor.selected, 1)
        self.assertIn("SEL 1", session.screen.to_text())

    def test_annulation_removes_a_bound_choice_item(self):
        session = make_session(home, choice_remove)
        session.navigate("975")
        self.assertEqual(session.state["items"], ["A", "B", "C"])

        session.feed(ANNULATION)
        self.assertEqual(session.state["items"], ["B", "C"])
        self.assertEqual(session.focused_region, "items")
        self.assertEqual(session.regions["items"].cursor.selected, 0)
        self.assertIn("B C", session.screen.to_text())

    def test_annulation_without_remove_is_a_no_op(self):
        session = make_session(home, choice_no_remove)
        session.navigate("976")
        session.feed(ANNULATION)
        self.assertEqual(session.focused_region, "items")
        self.assertIn("NO REMOVE", session.screen.to_text())

    def test_annulation_still_clears_a_form_field(self):
        self.session.feed(b"PAD")
        self.assertEqual(self.session.values["origin"], "PAD")
        self.session.feed(ANNULATION)
        self.assertEqual(self.session.values["origin"], "")

    def test_correction_reaches_on_key_for_a_choice_region(self):
        session = make_session(home, choice_correct)
        session.navigate("978")
        session.feed(CORRECTION)
        self.assertTrue(session.state["corrected"])
        self.assertIn("CORRECT", session.screen.to_text())

    def test_correction_still_backspaces_a_form_field(self):
        self.session.feed(b"PAD")
        self.session.feed(CORRECTION)
        self.assertEqual(self.session.values["origin"], "PA")

    def test_choice_text_commands_run_on_the_focused_choice(self):
        session = make_session(home, choice_commands)
        session.navigate("977")
        session.feed(b"*")
        self.assertEqual(session.state["moved"], "A")
        self.assertIn("MOVED A", session.screen.to_text())
        self.assertEqual(session.focused_region, "items")

    def test_unbound_choice_text_still_rings_the_bell(self):
        session = make_session(home, choice_commands)
        session.navigate("977")
        actions = session.feed(b"#")
        self.assertEqual(actions[0].raw, BEL)
        self.assertNotIn("moved", session.state)

    def test_choice_text_commands_do_not_steal_form_input(self):
        self.session.feed(b"*")
        self.assertEqual(self.session.values["origin"], "*")

    def test_choice_commit_and_page_back(self):
        session = make_session(home, choice_commit)
        session.navigate("971")
        session.feed(ENVOI)
        self.assertEqual(session.state["committed"], 0)

        session.feed(RETOUR)
        self.assertTrue(session.state["back"])

    def test_implicit_pager_still_wraps(self):
        session = make_session(home, implicit_pager)
        session.navigate("968")
        self.assertIn("main", session.regions)
        self.assertEqual(
            session.regions["main"].definition.kind, "pager"
        )
        session.feed(SUITE)
        self.assertEqual(session.pager.page_number, 2)
        session.feed(SUITE)
        self.assertEqual(session.pager.page_number, 1)

    def test_static_regions_reject_set_regions(self):
        @page(
            "961",
            regions=(Region("choices", kind="choice", page_size=2),),
        )
        def bad(ctx):
            ctx.set_regions(Region("choices", kind="choice"))
            return Screen()

        session = make_session(home, bad)
        with self.assertRaises(ValueError):
            session.navigate("961")

    def test_focused_region_is_valid_on_the_first_render_line(self):
        @page(
            "972",
            regions=(
                Region("a", kind="choice", next="b", page_size=2),
                Region("b", kind="choice", prev="a", page_size=2),
            ),
        )
        def first_line(ctx):
            screen = Screen()
            screen.text(0, 0, f"FIRST {ctx.focused_region}")
            ctx.set_choice(2, region="a")
            ctx.set_choice(2, region="b")
            return screen

        session = make_session(home, first_line)
        session.navigate("972")
        self.assertIn("FIRST a", session.screen.to_text())

    def test_choice_items_commit_automatically(self):
        def submit(ctx, line):
            ctx.state["committed"] = ctx.region("items").committed
            return "972"

        @page(
            "973",
            on_submit=submit,
            regions=(Region("items", kind="choice", page_size=2),),
        )
        def item_commit(ctx):
            ctx.set_choice(("A", "B", "C"), region="items")
            return Screen()

        session = make_session(home, item_commit)
        session.navigate("973")
        session.feed(ENVOI)
        self.assertEqual(session.state["committed"], "A")
        session.navigate("973")
        session.feed(SUITE)
        session.feed(ENVOI)
        self.assertEqual(session.state["committed"], "B")


class RegionValidationTests(unittest.TestCase):
    def _start(self, page_object):
        session = make_session(home, page_object)
        session.navigate(page_object.number)

    def test_duplicate_region_names(self):
        with self.assertRaises(ValueError):
            @page("962", regions=(Region("a"), Region("a")))
            def bad(ctx):
                return Screen()

    def test_unknown_edge(self):
        with self.assertRaises(ValueError):
            @page("963", regions=(Region("a", next="missing"),))
            def bad(ctx):
                return Screen()

    def test_default_focus_must_exist(self):
        with self.assertRaises(ValueError):
            @page(
                "964",
                regions=(Region("a"),),
                default_focus="missing",
            )
            def bad(ctx):
                return Screen()

    def test_named_page_requires_explicit_pager_region(self):
        @page(
            "965",
            regions=(
                Region("a", kind="pager", page_size=2),
                Region("b", kind="pager", page_size=2),
            ),
        )
        def bad(ctx):
            ctx.set_pager(3, 2)
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_each_region_needs_a_cursor(self):
        @page(
            "969",
            form=True,
            regions=(
                Region("form", kind="form", next="results"),
                Region("results", kind="pager", prev="form", page_size=2),
            ),
        )
        def bad(ctx):
            ctx.add_field("origin", 2, 2, 3, region="form")
            return Screen()

        with self.assertRaises(ValueError):
            self._start(bad)

    def test_named_form_requires_form_true(self):
        with self.assertRaises(ValueError):
            @page("966", regions=(Region("form", kind="form"),))
            def bad(ctx):
                return Screen()

    def test_named_page_requires_an_explicit_choice_region(self):
        @page(
            "967",
            regions=(
                Region("a", kind="choice", page_size=2),
                Region("b", kind="choice", page_size=2),
            ),
        )
        def bad(ctx):
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
        with self.assertRaises(ValueError):
            Region("a", kind="bogus")
        with self.assertRaises(ValueError):
            Region("a", kind="form", page_size=2)
        with self.assertRaises(ValueError):
            Region("a", wrap=True)


if __name__ == "__main__":
    unittest.main()
