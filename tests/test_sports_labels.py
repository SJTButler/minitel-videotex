import unittest
from datetime import datetime, timezone

from pages.sports.labels import alert_text, competition_label
from services.sports.models import Alert

NOW = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)


class SportsLabelTests(unittest.TestCase):
    def test_competition_label(self):
        self.assertEqual(competition_label("PL"), "PREMIER LEAGUE")
        self.assertEqual(competition_label("pl"), "PREMIER LEAGUE")
        self.assertEqual(competition_label("XYZ"), "XYZ")

    def test_alert_text(self):
        self.assertEqual(
            alert_text(Alert(NOW, "KO", 1, "ARS", "CHE")),
            "KO ARS V CHE",
        )
        self.assertEqual(
            alert_text(Alert(NOW, "HT", 1, "ARS", "CHE", 1, 0)),
            "HT ARS 1-0 CHE",
        )
        self.assertEqual(
            alert_text(Alert(NOW, "FT", 1, "ARS", "CHE", 2, 1)),
            "FT ARS 2-1 CHE",
        )
        self.assertEqual(
            alert_text(Alert(NOW, "GOAL", 1, "ARS", "CHE", 2, 1, 34)),
            "GOAL ARS 2-1 CHE 34'",
        )
        self.assertEqual(
            alert_text(Alert(NOW, "GOAL", 1, "ARS", "CHE", 2, 1, 45, 2)),
            "GOAL ARS 2-1 CHE 45+2'",
        )


if __name__ == "__main__":
    unittest.main()
