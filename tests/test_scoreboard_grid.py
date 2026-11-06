import unittest

from minitel import Screen
from pages.sports._support.scoreboard import (
    MAX_MATCHES,
    MatchCard,
    build_pages,
    draw_rows,
)


def card(kickoff, home, away, *, score="1-0", status="",
         live=False, order=0):
    return MatchCard(
        code="PL",
        kickoff=kickoff,
        home=home,
        away=away,
        score=score,
        status=status,
        live=live,
        order=order,
    )


class ScoreboardGridTests(unittest.TestCase):
    def test_groups_by_kickoff_and_draws_two_columns(self):
        cards = [
            card("15:00", "ARS", "CHE", live=True, status="67'", order=1),
            card("15:00", "LIV", "MCI", score="0-0", order=2),
            card("17:30", "EVE", "COV", score="v", order=3),
        ]
        pages = build_pages("PL", cards, lambda value: value)
        self.assertEqual(len(pages), 1)

        screen = Screen()
        draw_rows(screen, pages[0])
        lines = screen.to_text().splitlines()
        self.assertEqual(lines[4].strip(), "15:00")
        self.assertIn("ARS", lines[5])
        self.assertIn("LIV", lines[5])
        self.assertIn("67'", lines[5])
        self.assertEqual(lines[6].strip(), "17:30")
        self.assertIn("EVE", lines[7])

    def test_chunks_into_pages_at_the_row_limit(self):
        cards = [
            card(
                "15:00",
                f"H{index:02d}",
                f"A{index:02d}",
                order=index,
            )
            for index in range(MAX_MATCHES)
        ]
        pages = build_pages("PL", cards, lambda value: value)
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages[0].matches), 20)
        self.assertEqual(len(pages[1].matches), 2)
        self.assertEqual(pages[0].number, 1)
        self.assertEqual(pages[1].number, 2)
        self.assertEqual(pages[1].count, 2)


if __name__ == "__main__":
    unittest.main()
