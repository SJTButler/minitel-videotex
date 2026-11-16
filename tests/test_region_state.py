import unittest

from minitel import M1, Registry, Region, Screen, Session, page

SUITE = bytes([0x13, 0x48])


@page("950")
def home(ctx):
    return Screen()


def _stateful_choice_render(ctx):
    total = ctx.state.get("total", 3)
    ctx.set_regions(Region("list", key=ctx.state.get("key")))
    choice = ctx.set_choice(
        total,
        2,
        selected=ctx.state.get("selected"),
        reset=ctx.state.get("reset", False),
        region="list",
    )
    screen = Screen()
    screen.text(0, 0, f"SEL {choice.selected} PAGE {choice.label}")
    return screen


@page("980")
def stateful_choice(ctx):
    return _stateful_choice_render(ctx)


def _conditional_choice_render(ctx):
    screen = Screen()
    if ctx.state.get("hidden"):
        ctx.set_regions(Region("other", key="other"))
        other = ctx.set_choice(2, 2, region="other")
        screen.text(0, 0, f"OTHER {other.selected}")
        return screen
    ctx.set_regions(Region("list", key=ctx.state.get("key", "content")))
    choice = ctx.set_choice(5, 2, region="list")
    screen.text(0, 0, f"LIST {choice.selected} PAGE {choice.label}")
    return screen


@page("981")
def conditional_choice(ctx):
    return _conditional_choice_render(ctx)


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


class ChoiceRegionStateTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session(home, stateful_choice)
        self.session.navigate("980")

    def _move_to_last(self):
        for _ in range(4):
            self.session.feed(SUITE)
        self.assertEqual(self.session.regions["list"].cursor.selected, 2)

    def test_live_total_change_preserves_and_clamps_the_selection(self):
        self._move_to_last()
        self.session.state["total"] = 5
        self.session.refresh()
        self.assertEqual(self.session.regions["list"].cursor.selected, 2)

        self.session.state["total"] = 2
        self.session.refresh()
        choice = self.session.regions["list"].cursor
        self.assertEqual(choice.selected, 1)
        self.assertEqual(choice.page_index, 0)

    def test_key_change_resets_the_selection(self):
        self._move_to_last()
        self.session.state["key"] = "new"
        self.session.refresh()
        self.assertEqual(self.session.regions["list"].cursor.selected, 0)

    def test_reset_starts_the_selection_again(self):
        self._move_to_last()
        self.session.state["reset"] = True
        self.session.refresh()
        self.assertEqual(self.session.regions["list"].cursor.selected, 0)

    def test_explicit_selected_wins(self):
        self.session.state["total"] = 5
        self.session.state["selected"] = 4
        self.session.refresh()
        self.assertEqual(self.session.regions["list"].cursor.selected, 4)

        self.session.state["selected"] = 2
        self.session.refresh()
        self.assertEqual(self.session.regions["list"].cursor.selected, 2)

    def test_returning_to_a_remembered_key_restores_the_selection(self):
        self._move_to_last()
        self.session.state["key"] = "other"
        self.session.refresh()
        self.session.feed(SUITE)
        self.assertEqual(self.session.regions["list"].cursor.selected, 1)

        self.session.state["key"] = None
        self.session.refresh()
        self.assertEqual(self.session.regions["list"].cursor.selected, 2)

    def test_reset_wins_over_a_remembered_key(self):
        self._move_to_last()
        self.session.state["key"] = "other"
        self.session.refresh()
        self.session.feed(SUITE)

        self.session.state["key"] = None
        self.session.state["reset"] = True
        self.session.refresh()
        self.assertEqual(self.session.regions["list"].cursor.selected, 0)


class ConditionalChoiceStateTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session(home, conditional_choice)
        self.session.navigate("981")

    def test_removed_and_restored_region_restores_selection_and_page(self):
        for _ in range(3):
            self.session.feed(SUITE)
        choice = self.session.regions["list"].cursor
        self.assertEqual(choice.selected, 3)
        self.assertEqual(choice.page_index, 1)

        self.session.state["hidden"] = True
        self.session.refresh()
        self.assertNotIn("list", self.session.regions)

        self.session.state["hidden"] = False
        self.session.refresh()
        choice = self.session.regions["list"].cursor
        self.assertEqual(choice.selected, 3)
        self.assertEqual(choice.page_index, 1)

    def test_changed_key_starts_a_fresh_selection(self):
        for _ in range(3):
            self.session.feed(SUITE)
        self.session.state["key"] = "another"
        self.session.refresh()
        choice = self.session.regions["list"].cursor
        self.assertEqual(choice.selected, 0)
        self.assertEqual(choice.page_index, 0)


if __name__ == "__main__":
    unittest.main()
