import unittest

from minitel import M1, PAGE_BACK, Registry, Region, Screen, Session, page

from pages.common.widgets import line_field

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])


@page("950")
def home(ctx):
    return Screen()


def _three_kind_render(ctx):
    items = tuple(
        ctx.state.get("items", ("ALPHA", "BETA", "GAMMA", "DELTA"))
    )
    ctx.set_regions(
        Region("form", next="choices"),
        Region(
            "choices",
            next="results",
            prev="form",
            commit=lambda choice: (
                items[choice.selected]
                if choice.selected is not None
                and 0 <= choice.selected < len(items)
                else None
            ),
            key=ctx.state.get("choice_key"),
        ),
        Region(
            "results",
            prev="choices",
            activate="stay",
            key=ctx.state.get("result_key", "results"),
        ),
    )
    screen = Screen()
    screen.text(0, 0, f"FOCUS {ctx.focused_region}")
    line_field(screen, ctx, "query", 2, 2, 3, label="Q:", region="form")
    choice = ctx.set_choice(len(items), 2, region="choices")
    pager = ctx.set_pager(6, 2, region="results")
    selected = (
        items[choice.selected] if choice.selected is not None else "-"
    )
    screen.text(3, 0, f"SEL {choice.selected} {selected}")
    screen.text(4, 0, f"PAGE {pager.label}")
    screen.text(5, 0, f"COMMITTED {ctx.region('choices').committed}")
    return screen


def _three_kind_form(ctx, values):
    if ctx.focused_region == "form":
        ctx.state["submits"] = ctx.state.get("submits", 0) + 1
        ctx.focus_region("choices")
    elif ctx.focused_region == "choices":
        ctx.state["picked"] = ctx.region("choices").committed
        ctx.focus_region("results")
    return "982"


@page(
    "982",
    form=True,
    on_form=_three_kind_form,
    on_tick=_three_kind_render,
    tick_interval=1.0,
)
def three_kind(ctx):
    return _three_kind_render(ctx)


def _three_choice_render(ctx):
    ctx.set_regions(
        Region("a", next="c", prev=PAGE_BACK, key="a"),
        Region("b", next="a", prev="a", key="b"),
        Region("c", prev="b", key="c"),
    )
    a = ctx.set_choice(2, 2, region="a")
    b = ctx.set_choice(2, 2, region="b")
    c = ctx.set_choice(2, 2, region="c")
    screen = Screen()
    screen.text(0, 0, f"FOCUS {ctx.focused_region}")
    screen.text(1, 0, f"A {a.selected} B {b.selected} C {c.selected}")
    return screen


def _three_choice_back(ctx):
    ctx.state["backs"] = ctx.state.get("backs", 0) + 1
    return True


@page("983", on_back=_three_choice_back)
def three_choice(ctx):
    return _three_choice_render(ctx)


def _conditional_focus_render(ctx):
    show = not ctx.state.get("hide_middle", False)
    regions = [Region("folders", next="messages" if show else "reply")]
    if show:
        regions.append(Region("messages", next="reply", prev=PAGE_BACK))
    regions.append(Region("reply", prev="messages" if show else "folders"))
    ctx.set_regions(*regions)
    screen = Screen()
    screen.text(0, 0, f"FOCUS {ctx.focused_region}")
    folders = ctx.set_choice(2, 2, region="folders")
    screen.text(2, 0, f"FOLDERS {folders.selected}")
    if show:
        messages = ctx.set_choice(2, 2, region="messages")
        screen.text(3, 0, f"MESSAGES {messages.selected}")
    reply = ctx.set_choice(2, 2, region="reply")
    screen.text(4, 0, f"REPLY {reply.selected}")
    return screen


def _conditional_focus_back(ctx):
    ctx.state["backs"] = ctx.state.get("backs", 0) + 1
    return True


@page("984", on_back=_conditional_focus_back)
def conditional_focus(ctx):
    return _conditional_focus_render(ctx)


def make_session(*pages, initial="950"):
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


class ThreeRegionConformanceTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session(home, three_kind)
        self.session.navigate("982")

    def test_form_choice_pager_route_and_commit(self):
        self.assertEqual(self.session.focused_region, "form")
        self.session.feed(b"PAD" + ENVOI)
        self.assertEqual(self.session.focused_region, "choices")
        self.assertEqual(self.session.state["submits"], 1)

        self.session.feed(SUITE)
        self.session.feed(ENVOI)
        self.assertEqual(self.session.focused_region, "results")
        self.assertEqual(self.session.state["picked"], "BETA")

        self.session.feed(SUITE)
        self.assertEqual(
            self.session.regions["results"].cursor.page_index, 1
        )
        self.session.feed(RETOUR)
        self.assertEqual(
            self.session.regions["results"].cursor.page_index, 0
        )
        self.session.feed(RETOUR)
        self.assertEqual(self.session.focused_region, "choices")
        self.assertEqual(self.session.regions["choices"].cursor.selected, 1)

        self.session.feed(RETOUR)
        self.session.feed(RETOUR)
        self.assertEqual(self.session.focused_region, "form")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "950")

    def test_tick_reuses_selection_and_refreshed_commit(self):
        self.session.feed(b"PAD" + ENVOI)
        self.session.feed(SUITE)
        self.session.state["items"] = (
            "ZULU", "ALPHA", "BETA", "GAMMA", "DELTA",
        )
        self.session.tick()
        self.assertIsNone(self.session.page_error)
        self.assertEqual(
            self.session.regions["choices"].cursor.selected, 1
        )

        self.session.feed(ENVOI)
        self.assertEqual(self.session.state["picked"], "ALPHA")
        self.assertEqual(self.session.focused_region, "results")


class ThreeChoiceConformanceTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session(home, three_choice)
        self.session.navigate("983")

    def test_non_linear_focus_graph_and_page_back(self):
        self.assertEqual(self.session.focused_region, "a")
        self.session.feed(RETOUR)
        self.assertEqual(self.session.state["backs"], 1)
        self.assertEqual(self.session.focused_region, "a")

        self.session.feed(SUITE)
        self.session.feed(SUITE)
        self.assertEqual(self.session.focused_region, "c")

        self.session.feed(RETOUR)
        self.assertEqual(self.session.focused_region, "b")

        self.session.feed(SUITE)
        self.session.feed(SUITE)
        self.assertEqual(self.session.focused_region, "a")

        self.session.feed(RETOUR)
        self.session.feed(RETOUR)
        self.assertEqual(self.session.state["backs"], 2)
        self.assertEqual(self.session.focused_region, "a")


class ConditionalFocusConformanceTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session(home, conditional_focus)
        self.session.navigate("984")

    def test_conditional_region_retour_boundary(self):
        self.session.feed(SUITE)
        self.session.feed(SUITE)
        self.assertEqual(self.session.focused_region, "messages")

        self.session.feed(RETOUR)
        self.assertEqual(self.session.state["backs"], 1)
        self.assertEqual(self.session.focused_region, "messages")

    def test_missing_focus_falls_back_to_a_declared_region(self):
        self.session.feed(SUITE)
        self.session.feed(SUITE)
        self.assertEqual(self.session.focused_region, "messages")

        self.session.state["hide_middle"] = True
        self.session.refresh()
        self.assertNotIn("messages", self.session.regions)
        self.assertEqual(self.session.focused_region, "folders")

        self.session.state["hide_middle"] = False
        self.session.refresh()
        self.assertEqual(self.session.focused_region, "folders")

        self.session.feed(SUITE)
        self.assertEqual(self.session.focused_region, "messages")


if __name__ == "__main__":
    unittest.main()
