import unittest

from minitel import M1, Screen, page
from minitel.pagemodel import Registry
from minitel.session import Session


class Resource:
    def __init__(self, name, events, *, fail=False):
        self.name = name
        self.events = events
        self.fail = fail
        self.closed = 0

    def close(self):
        self.closed += 1
        self.events.append(self.name)
        if self.fail:
            raise RuntimeError(self.name)


def make_session():
    registry = Registry()

    @page("100")
    def home(ctx):
        return Screen()

    registry.add(home)
    session = Session(registry, M1, initial="100")
    session.start()
    return session


class SessionResourceTests(unittest.TestCase):
    def test_closes_in_reverse_order_and_is_idempotent(self):
        events = []
        session = make_session()
        first = Resource("first", events)
        second = Resource("second", events)
        session.add_resource(first)
        session.add_resource(second)
        session.add_resource(first)

        session.close()
        session.close()

        self.assertEqual(events, ["second", "first"])
        self.assertEqual(first.closed, 1)
        self.assertEqual(second.closed, 1)

    def test_closes_all_resources_even_after_an_error(self):
        events = []
        session = make_session()
        session.add_resource(Resource("bad", events, fail=True))
        session.add_resource(Resource("good", events))

        with self.assertRaises(RuntimeError):
            session.close()

        self.assertEqual(events, ["good", "bad"])

    def test_cannot_add_a_resource_after_close(self):
        session = make_session()
        session.close()
        with self.assertRaises(RuntimeError):
            session.add_resource(Resource("late", []))


if __name__ == "__main__":
    unittest.main()
