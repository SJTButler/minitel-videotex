import asyncio
import unittest
from datetime import datetime, timezone

from minitel.http import HttpError
from pages.sports.config import SportsConfig
from pages.sports.feed import SportsService
from pages.sports.models import Match, MatchStatus, StandingRow, Team
from pages.sports.source import FetchResult

KICKOFF = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)


def immediate(target, args):
    class Thread:
        def start(self):
            target(*args)

    return Thread()


def match(match_id=1, status=MatchStatus.LIVE, home_goals=1,
          away_goals=0, minute=34, kickoff=KICKOFF):
    return Match(
        id=match_id,
        competition_id=2021,
        competition_code="PL",
        competition_name="PREMIER LEAGUE",
        home=Team(57, "ARSENAL", "ARS"),
        away=Team(61, "CHELSEA", "CHE"),
        kickoff=kickoff,
        status=status,
        minute=minute,
        home_goals=home_goals,
        away_goals=away_goals,
    )


class FakeSource:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0
        self.standings_calls = 0
        self.standings_value = ()

    def fetch_day(self, date):
        self.calls += 1
        result = self.results[min(self.calls - 1, len(self.results) - 1)]
        if isinstance(result, Exception):
            raise result
        return result

    def fetch_standings(self, code):
        self.standings_calls += 1
        return FetchResult(self.standings_value)


def service(source, **kwargs):
    config = SportsConfig(
        token="test-token",
        live_interval=60.0,
        day_interval=900.0,
        idle_interval=1800.0,
        retry_delay=30.0,
    )
    return SportsService(
        config=config,
        source=source,
        clock=lambda: 100.0,
        wall_clock=lambda: 1000.0,
        thread_factory=immediate,
        **kwargs,
    )


class FeedTests(unittest.TestCase):
    def test_first_snapshot_has_no_alerts(self):
        source = FakeSource([FetchResult((match(),))])
        feed = service(source)
        asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertTrue(snapshot.has_value)
        self.assertEqual(len(snapshot.matches), 1)
        self.assertEqual(snapshot.alerts, ())
        self.assertEqual(feed.poll_delay(), 60.0)

    def test_goal_alert_and_dedupe(self):
        source = FakeSource([
            FetchResult((match(home_goals=1),)),
            FetchResult((match(home_goals=2, minute=40),)),
            FetchResult((match(home_goals=2, minute=45),)),
        ])
        feed = service(source)
        asyncio.run(feed.refresh_once())
        asyncio.run(feed.refresh_once())
        asyncio.run(feed.refresh_once())

        alerts = feed.snapshot().alerts
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].kind, "GOAL")
        self.assertIn("GOAL ARS 2-0 CHE", alerts[0].text)
        self.assertIn("40'", alerts[0].text)

    def test_finished_alert(self):
        source = FakeSource([
            FetchResult((match(home_goals=2),)),
            FetchResult((
                match(status=MatchStatus.FINISHED, home_goals=2, minute=90),
            )),
        ])
        feed = service(source)
        asyncio.run(feed.refresh_once())
        asyncio.run(feed.refresh_once())

        alerts = feed.snapshot().alerts
        self.assertEqual(alerts[0].kind, "FT")
        self.assertEqual(alerts[0].text, "FT ARS 2-0 CHE")

    def test_kickoff_and_half_time_alerts(self):
        scheduled = match(
            status=MatchStatus.SCHEDULED,
            home_goals=None,
            away_goals=None,
            minute=None,
        )
        source = FakeSource([
            FetchResult((scheduled,)),
            FetchResult((match(home_goals=0, away_goals=0, minute=1),)),
            FetchResult((
                match(status=MatchStatus.HALF_TIME, home_goals=0,
                      away_goals=0, minute=45),
            )),
        ])
        feed = service(source)
        asyncio.run(feed.refresh_once())
        asyncio.run(feed.refresh_once())
        asyncio.run(feed.refresh_once())

        kinds = [alert.kind for alert in feed.snapshot().alerts]
        self.assertEqual(kinds, ["HT", "KO"])

    def test_error_keeps_last_snapshot(self):
        source = FakeSource([
            FetchResult((match(),)),
            HttpError("https://example.test/", status=429, retry_after=120),
        ])
        feed = service(source)
        asyncio.run(feed.refresh_once())
        delay = asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertEqual(delay, 120.0)
        self.assertTrue(snapshot.has_value)
        self.assertEqual(len(snapshot.matches), 1)
        self.assertIn("HTTP 429", snapshot.error)

    def test_poll_delay_uses_state(self):
        feed = service(FakeSource([FetchResult((match(),))]))
        asyncio.run(feed.refresh_once())
        self.assertEqual(feed.poll_delay(), 60.0)

        soon = datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc)
        feed._apply(FetchResult((
            match(
                status=MatchStatus.SCHEDULED,
                home_goals=None,
                away_goals=None,
                minute=None,
                kickoff=datetime(
                    2026, 11, 1, 15, 0, tzinfo=timezone.utc
                ),
            ),
        )))
        self.assertEqual(feed.poll_delay(now=soon), 900.0)

        feed._apply(FetchResult((
            match(
                status=MatchStatus.FINISHED,
                home_goals=2,
                minute=90,
            ),
        )))
        self.assertEqual(feed.poll_delay(now=soon), 1800.0)

        feed._apply(FetchResult((match(),), quota_remaining=1))
        self.assertEqual(feed.poll_delay(now=soon), 1800.0)

    def test_standings_are_cached(self):
        source = FakeSource([FetchResult(())])
        source.standings_value = (
            StandingRow(1, Team(57, "ARSENAL", "ARS"), 10, 13, 25),
        )
        feed = service(source)
        feed.standings("PL")
        first = feed.standings_cache.snapshot("PL")
        feed.standings("PL")

        self.assertTrue(first.has_value)
        self.assertEqual(first.value[0].points, 25)
        self.assertEqual(source.standings_calls, 1)

    def test_not_configured(self):
        feed = SportsService(config=SportsConfig(token=""), source=None)
        self.assertFalse(feed.configured)
        self.assertFalse(feed.snapshot().loading)
        self.assertEqual(feed.standings("PL").error.__class__, RuntimeError)


if __name__ == "__main__":
    unittest.main()
