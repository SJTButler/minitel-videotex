import unittest

from minitel.pages import Registry, page
from minitel.profiles import M1
from minitel.screen import Screen
from minitel.session import Session


class CursorConflictTests(unittest.TestCase):
    def make_session(self, page_object):
        registry = Registry()
        registry.add(page_object)
        session = Session(
            registry,
            M1,
            initial=page_object.number,
            fallback=page_object,
        )
        return session

    def test_form_with_pager_is_rejected_when_fields_are_added_first(self):
        @page("950", form=True)
        def bad(ctx):
            ctx.set_input(1, 0, 5)
            ctx.set_pager(4, 2)
            return Screen()

        session = self.make_session(bad)
        with self.assertRaises(ValueError):
            session.start()

    def test_form_with_pager_is_rejected_when_pager_is_added_first(self):
        @page("951", form=True)
        def bad(ctx):
            ctx.set_pager(4, 2)
            ctx.set_input(1, 0, 5)
            return Screen()

        session = self.make_session(bad)
        with self.assertRaises(ValueError):
            session.start()

    def test_single_input_plus_pager_is_allowed(self):
        @page("952")
        def allowed(ctx):
            ctx.set_pager(4, 2)
            ctx.set_input(1, 0, 5)
            return Screen()

        session = self.make_session(allowed)
        screen = session.start()
        self.assertIsNotNone(session.pager)
        self.assertIsInstance(screen, Screen)


if __name__ == "__main__":
    unittest.main()
