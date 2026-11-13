import unittest
from types import SimpleNamespace

from minitel import (
    Announcement,
    AnnouncementPolicy,
    FunctionPage,
    M1,
    Registry,
    Screen,
    Session,
)
from pages.common.header import CHYRON_WIDTH, ChyronHeader


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def row0(screen):
    return "".join(cell.ch for cell in screen.rows[0])


def context(*, announcement=None, elapsed=0.0, status="PAGE 700"):
    return SimpleNamespace(
        announcement=announcement,
        announcement_elapsed=elapsed,
        screensaver_active=False,
        status_text=status,
        body_row=tuple(Screen().rows[0]),
        body_page=SimpleNamespace(number="700"),
    )


class ChyronRenderTests(unittest.TestCase):
    def test_text_enters_from_the_right_and_moves_left(self):
        header = ChyronHeader()
        first = header.render(
            context(
                announcement=Announcement("k", "GOAL ARS 1-0 CHE"),
                elapsed=0.0,
            )
        )
        self.assertEqual(row0(first)[CHYRON_WIDTH - 1], "G")
        self.assertEqual(row0(first)[:CHYRON_WIDTH - 1].strip(), "")
        self.assertEqual(row0(first)[CHYRON_WIDTH:].strip(), "")

        moved = header.render(
            context(
                announcement=Announcement("k", "GOAL ARS 1-0 CHE"),
                elapsed=1.0,
            )
        )
        self.assertEqual(row0(moved)[CHYRON_WIDTH - 3], "G")
        self.assertEqual(row0(moved)[:CHYRON_WIDTH - 3].strip(), "")
        self.assertEqual(row0(moved)[CHYRON_WIDTH:].strip(), "")

    def test_it_falls_back_to_the_status_when_idle(self):
        screen = ChyronHeader().render(context(status="PAGE 700"))
        self.assertIn("PAGE 700", row0(screen))

    def test_duration_covers_the_text_travel(self):
        header = ChyronHeader()
        duration = header.announcement_duration(
            Announcement("k", "GOAL ARS 1-0 CHE")
        )
        expected = (
            len("GOAL ARS 1-0 CHE") + CHYRON_WIDTH - 1
        ) / 2.0
        self.assertEqual(duration, max(12.0, expected))


class ChyronSessionTests(unittest.TestCase):
    def test_header_tick_advances_the_chyron(self):
        events = []
        clock = Clock()

        def body(ctx):
            screen = Screen()
            screen.text(1, 0, "BODY")
            ctx.set_status("PAGE 700")
            return screen

        page = FunctionPage(
            "700", body, announce=lambda ctx: tuple(events)
        )
        registry = Registry()
        registry.add(page)
        session = Session(
            registry,
            M1,
            initial="700",
            fallback=page,
            header=ChyronHeader(),
            announcement_policy=AnnouncementPolicy(
                poll=5.0, show=12.0, gap=2.0
            ),
            clock=clock,
            wall_clock=clock,
        )
        session.start()
        session.on_timeout()

        clock.advance(5.0)
        events.append(Announcement("a", "GOAL A", at=5.0))
        session.on_timeout()
        self.assertEqual(row0(session.screen)[CHYRON_WIDTH - 1], "G")

        clock.advance(1.0)
        session.on_timeout()
        self.assertEqual(row0(session.screen)[CHYRON_WIDTH - 3], "G")


if __name__ == "__main__":
    unittest.main()
