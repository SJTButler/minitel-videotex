import unittest

import pages

from minitel import (
    Announcement,
    AnnouncementPolicy,
    FunctionPage,
    M1,
    Registry,
    Screen,
    Session,
)
from minitel.session import Screensaver
from pages.common.header import AnnouncementHeader, StatusHeader


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def body(ctx):
    screen = Screen()
    screen.text(1, 0, "BODY")
    ctx.set_status("PAGE 700")
    ctx.set_input(5, 0, 4)
    return screen


def saver(ctx):
    screen = Screen()
    screen.text(0, 0, "SAVER")
    return screen


SAVER = FunctionPage("720", saver, screensaver="diagnostic")


def build_registry(events):
    registry = Registry()
    registry.add(
        FunctionPage(
            "700", body, announce=lambda ctx: tuple(events)
        )
    )
    return registry


def make_session(events, *, header=None, policy=None, screensaver=False):
    clock = Clock()
    log = []
    registry = build_registry(events)
    screensaver_obj = None
    if screensaver:
        registry.add(SAVER)
        screensaver_obj = Screensaver.from_spec(
            registry, (SAVER,), after=10.0, hold=5.0
        )
    session = Session(
        registry,
        M1,
        initial="700",
        fallback=registry.get("700"),
        header=header if header is not None else StatusHeader(),
        announcement_policy=policy or AnnouncementPolicy(
            poll=5.0, show=10.0, gap=2.0
        ),
        screensaver=screensaver_obj,
        clock=clock,
        wall_clock=clock,
        log=log.append,
    )
    session.start()
    return session, clock, log


def row0(screen):
    return "".join(cell.ch for cell in screen.rows[0]).strip()


class AnnouncementQueueTests(unittest.TestCase):
    def test_announcement_shows_then_restores_the_status(self):
        events = []
        session, clock, log = make_session(events)
        self.assertEqual(session.next_timeout(), 0.0)
        session.on_timeout()
        self.assertIsNone(session.announcement)

        clock.advance(5.0)
        events.append(Announcement("a", "GOAL A", at=5.0))
        session.on_timeout()
        self.assertEqual(session.announcement.text, "GOAL A")
        self.assertEqual(session.announcement_channel, "700")
        self.assertIn("ANNOUNCE show 700 <- 700", log)
        self.assertIn("GOAL A", row0(session.screen))

        clock.advance(10.0)
        session.on_timeout()
        self.assertIsNone(session.announcement)
        self.assertIn("PAGE 700", row0(session.screen))
        self.assertIn("ANNOUNCE hide 700 <- 700", log)

    def test_queue_drains_in_time_order(self):
        events = []
        session, clock, _ = make_session(events)
        session.on_timeout()

        clock.advance(5.0)
        events.extend(
            (
                Announcement("b", "GOAL B", at=6.0),
                Announcement("a", "GOAL A", at=5.0),
            )
        )
        session.on_timeout()
        self.assertEqual(session.announcement.text, "GOAL A")

        clock.advance(10.0)
        session.on_timeout()
        self.assertIsNone(session.announcement)
        clock.advance(2.0)
        session.on_timeout()
        self.assertEqual(session.announcement.text, "GOAL B")

    def test_typing_defers_the_next_announcement(self):
        events = []
        session, clock, _ = make_session(events)
        session.on_timeout()
        session.values[session.fields[0].name] = "X"

        clock.advance(5.0)
        events.append(Announcement("a", "GOAL A", at=5.0))
        session.on_timeout()
        self.assertIsNone(session.announcement)

        session.values[session.fields[0].name] = ""
        clock.advance(5.0)
        session.on_timeout()
        self.assertEqual(session.announcement.text, "GOAL A")

    def test_pause_clears_the_current_and_queued_announcements(self):
        events = []
        session, clock, _ = make_session(events)
        session.on_timeout()
        clock.advance(5.0)
        events.extend(
            (
                Announcement("a", "GOAL A", at=5.0),
                Announcement("b", "GOAL B", at=6.0),
            )
        )
        session.on_timeout()
        self.assertIsNotNone(session.announcement)

        session.pause()
        self.assertIsNone(session.announcement)
        self.assertEqual(session._announcement_queue, [])
        session.resume()
        self.assertIsNone(session.announcement)

    def test_announcement_header_passes_through_without_a_current(self):
        events = []
        session, clock, _ = make_session(
            events, header=AnnouncementHeader()
        )
        session.on_timeout()
        self.assertEqual(row0(session.screen), "")

        clock.advance(5.0)
        events.append(Announcement("a", "GOAL A", at=5.0))
        session.on_timeout()
        self.assertEqual(row0(session.screen), "GOAL A")

    def test_status_header_renders_on_the_screensaver_and_survives_wake(self):
        events = []
        registry_session, clock, _ = make_session(
            events, screensaver=True
        )
        registry_session.on_timeout()
        registry_session.activate_screensaver()
        self.assertTrue(registry_session.screensaver_active)

        clock.advance(5.0)
        events.append(Announcement("a", "GOAL A", at=5.0))
        registry_session.on_timeout()
        self.assertEqual(row0(registry_session.screen), "GOAL A")

        registry_session.wake()
        self.assertEqual(row0(registry_session.screen), "GOAL A")

    def test_reader_still_uses_the_announcement_header(self):
        self.assertIsInstance(
            pages.build_registry().get("160").header, AnnouncementHeader
        )


if __name__ == "__main__":
    unittest.main()
