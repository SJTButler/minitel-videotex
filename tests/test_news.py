import time
import unittest

import pages

from minitel import profiles
from minitel.cache import Snapshot
from minitel.session import Session
from pages.common.layout import ACCENT, SECONDARY, WARNING
from services.news import Story

ENVOI = bytes([0x13, 0x41])


def loaded(stories):
    return Snapshot(value=stories, loaded_at=time.monotonic())


class FakeService:
    def __init__(self, *snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    def front_page(self):
        index = min(self.calls, len(self.snapshots) - 1)
        self.calls += 1
        return self.snapshots[index]


def make_session(services=None):
    registry = pages.build_registry()
    session = Session(
        registry,
        profiles.M1,
        initial=pages.INITIAL,
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
        services=services,
    )
    session.start()
    return session


class DirectoryTests(unittest.TestCase):
    def test_lists_hacker_news_with_status(self):
        service = FakeService(loaded([Story(1, "One")]))
        session = make_session({"hackernews": service})
        session.navigate("110")
        screen = session.screen
        text = screen.to_text().splitlines()
        self.assertTrue(text[4].startswith("1  HACKER NEWS"))
        self.assertIn("UPDATED", text[5])
        self.assertEqual(screen.rows[4][0].fg, ACCENT)
        self.assertTrue(screen.rows[4][0].inverse)
        self.assertEqual(screen.rows[5][2].fg, SECONDARY)
        self.assertTrue(screen.rows[5][2].underline)

    def test_not_configured(self):
        session = make_session()
        session.navigate("110")
        self.assertIn("NOT CONFIGURED", session.screen.to_text())

    def test_loading_status(self):
        service = FakeService(Snapshot(loading=True))
        session = make_session({"hackernews": service})
        session.navigate("110")
        self.assertIn("LOADING", session.screen.to_text())

    def test_unavailable_status(self):
        service = FakeService(Snapshot(error=RuntimeError("offline")))
        session = make_session({"hackernews": service})
        session.navigate("110")
        self.assertIn("UNAVAILABLE", session.screen.to_text())
        self.assertEqual(session.screen.rows[5][2].fg, WARNING)

    def test_offline_cached_status(self):
        service = FakeService(
            Snapshot(
                value=[Story(1, "One")],
                loaded_at=time.monotonic(),
                error=RuntimeError("offline"),
            )
        )
        session = make_session({"hackernews": service})
        session.navigate("110")
        self.assertIn("OFFLINE - CACHED", session.screen.to_text())

    def test_no_headlines_status(self):
        service = FakeService(loaded([]))
        session = make_session({"hackernews": service})
        session.navigate("110")
        self.assertIn("NO HEADLINES", session.screen.to_text())

    def test_number_opens_hacker_news(self):
        service = FakeService(loaded([Story(1, "One")]))
        session = make_session({"hackernews": service})
        session.navigate("110")
        session.feed(b"1" + ENVOI)
        self.assertEqual(session.current.number, "111")

    def test_other_number_still_routes(self):
        service = FakeService(loaded([Story(1, "One")]))
        session = make_session({"hackernews": service})
        session.navigate("110")
        session.feed(b"2" + ENVOI)
        self.assertEqual(session.current.number, "120")

    def test_background_load_changes_status_on_tick(self):
        service = FakeService(
            Snapshot(loading=True),
            loaded([Story(1, "One")]),
        )
        session = make_session({"hackernews": service})
        session.navigate("110")
        self.assertIn("LOADING", session.screen.to_text())

        session.tick()
        self.assertIn("UPDATED", session.screen.to_text())


if __name__ == "__main__":
    unittest.main()
