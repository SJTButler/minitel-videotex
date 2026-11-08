import unittest

from minitel.design.choice import Choice
from minitel.design.pager import Pager
from minitel.pagemodel import LINE_FIELD, Registry, page
from minitel.render import Screen
from minitel.session import Session
from minitel.terminal.profiles import M1

SUITE = bytes([0x13, 0x48])
RETOUR = bytes([0x13, 0x42])
ITEMS = tuple(f"R{index}" for index in range(10))


class ChoiceValueTests(unittest.TestCase):
    def test_window_and_page_crossing(self):
        choice = Choice(Pager(10, 3))
        choice = choice.clamp()
        self.assertEqual(choice.selected, 0)
        self.assertEqual(choice.label, "1/4")
        self.assertEqual(choice.window(ITEMS), ("R0", "R1", "R2"))
        choice = choice.next().next().next()
        self.assertEqual(choice.selected, 3)
        self.assertEqual(choice.label, "2/4")
        self.assertEqual(choice.window(ITEMS), ("R3", "R4", "R5"))
        choice = choice.prev()
        self.assertEqual(choice.selected, 2)
        self.assertEqual(choice.label, "1/4")

    def test_clamp_and_wrap(self):
        choice = Choice(Pager(10, 3), selected=99).clamp()
        self.assertEqual(choice.selected, 9)
        self.assertEqual(choice.label, "4/4")
        self.assertEqual(choice.next().selected, 9)
        wrapped = Choice(Pager(10, 3), selected=9, wrap=True)
        self.assertEqual(wrapped.next().selected, 0)
        self.assertEqual(Choice(Pager(0, 3)).clamp().selected, None)


class ChoiceSessionTests(unittest.TestCase):
    def make_session(self):
        @page("970")
        def paged(ctx):
            choice = ctx.set_choice(10, 3)
            screen = Screen()
            screen.text(0, 0, f"PAGE {choice.label} SEL {choice.selected}")
            for index, item in enumerate(choice.window(ITEMS)):
                selected = choice.selected == choice.offset + index
                screen.text(1 + index, 0, item, inverse=selected)
            ctx.set_input(5, 0, 10, live=True, value="Q")
            return screen

        @page("100")
        def home(ctx):
            return Screen()

        registry = Registry()
        registry.add(paged)
        registry.add(home)
        session = Session(registry, M1, initial="970", fallback=home)
        session.start()
        return session

    def test_selection_crosses_the_outer_page(self):
        session = self.make_session()
        self.assertEqual(session.choice.selected, 0)
        session.feed(SUITE)
        self.assertEqual(session.choice.selected, 1)
        session.feed(SUITE)
        session.feed(SUITE)
        self.assertEqual(session.choice.selected, 3)
        self.assertEqual(session.choice.pager.label, "2/4")
        self.assertEqual(session.values[LINE_FIELD], "Q")

    def test_retour_at_first_follows_history(self):
        session = self.make_session()
        session.navigate("100")
        session.navigate("970")
        self.assertEqual(session.choice.selected, 0)
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "100")

    def test_selection_clamps_at_last(self):
        session = self.make_session()
        for _ in range(12):
            session.feed(SUITE)
        self.assertEqual(session.choice.selected, 9)
        self.assertEqual(session.choice.pager.label, "4/4")


if __name__ == "__main__":
    unittest.main()
