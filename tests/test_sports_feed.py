import asyncio
import unittest
from datetime import datetime, timezone

from minitel.data.http import HttpError
from services.sports.config import SportsConfig
from services.sports.feed import SportsService
from services.sports.models import Alert, Goal, Match, MatchStatus, StandingRow, Team
from services.sports.source import FetchResult

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
    def __init__(self, results, range_results=None):
        self.results = list(results)
        self.range_results = list(range_results or [])
        self.calls = 0
        self.range_calls = 0
        self.range_dates = []
        self.standings_calls = 0
        self.standings_value = ()

    def fetch_day(self, date):
        self.calls += 1
        result = self.results[min(self.calls - 1, len(self.results) - 1)]
        if isinstance(result, Exception):
            raise result
        return result

    def fetch_range(self, start, end):
        self.range_calls += 1
        self.range_dates.append((start, end))
        if self.range_results:
            result = self.range_results[
                min(self.range_calls - 1, len(self.range_results) - 1)
            ]
        else:
            result = FetchResult(())
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
    kwargs.setdefault("today", lambda: "2026-11-01")
    return SportsService(
        config=config,
        source=source,
        clock=lambda: 100.0,
        wall_clock=lambda: 1000.0,
        thread_factory=immediate,
        **kwargs,
    )


class FeedTests(unittest.TestCase):
    def test_alert_history_is_bounded(self):
        feed = service(FakeSource([FetchResult((match(),))]))
        for minute in range(250):
            feed._alert(
                Alert(
                    KICKOFF,
                    "GOAL",
                    1,
                    "ARS",
                    "CHE",
                    2,
                    1,
                    minute,
                )
            )
        self.assertEqual(len(feed._alerts), 200)
        self.assertEqual(feed._alerts[0].minute, 249)
        self.assertEqual(feed._alerts[-1].minute, 50)

    def test_first_snapshot_has_no_alerts_before_kickoff(self):
        source = FakeSource([
            FetchResult((
                match(
                    status=MatchStatus.SCHEDULED,
                    home_goals=None,
                    away_goals=None,
                    minute=None,
                ),
            )),
        ])
        feed = service(source)
        asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertTrue(snapshot.has_value)
        self.assertEqual(len(snapshot.matches), 1)
        self.assertEqual(snapshot.alerts, ())
        self.assertEqual(feed.poll_delay(), 1800.0)

    def test_empty_today_falls_back_to_next_matchday(self):
        source = FakeSource(
            [FetchResult(())],
            range_results=[
                FetchResult((
                    match(
                        match_id=3,
                        status=MatchStatus.SCHEDULED,
                        home_goals=None,
                        away_goals=None,
                        minute=None,
                        kickoff=datetime(
                            2026, 11, 3, 15, 0, tzinfo=timezone.utc
                        ),
                    ),
                    match(
                        match_id=2,
                        status=MatchStatus.SCHEDULED,
                        home_goals=None,
                        away_goals=None,
                        minute=None,
                        kickoff=datetime(
                            2026, 11, 2, 15, 0, tzinfo=timezone.utc
                        ),
                    ),
                    match(
                        match_id=4,
                        status=MatchStatus.SCHEDULED,
                        home_goals=None,
                        away_goals=None,
                        minute=None,
                        kickoff=datetime(
                            2026, 11, 3, 20, 0, tzinfo=timezone.utc
                        ),
                    ),
                )),
            ],
        )
        feed = service(source)
        asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertTrue(snapshot.upcoming)
        self.assertEqual(snapshot.match_date, "2026-11-02")
        self.assertEqual([item.id for item in snapshot.matches], [2])
        self.assertEqual(source.range_calls, 1)
        self.assertEqual(
            source.range_dates[0], ("2026-11-02", "2026-11-12")
        )

    def test_fallback_searches_a_second_window(self):
        source = FakeSource(
            [FetchResult(())],
            range_results=[
                FetchResult(()),
                FetchResult((
                    match(
                        match_id=5,
                        status=MatchStatus.SCHEDULED,
                        home_goals=None,
                        away_goals=None,
                        minute=None,
                        kickoff=datetime(
                            2026, 11, 15, 15, 0, tzinfo=timezone.utc
                        ),
                    ),
                )),
            ],
        )
        feed = service(source)
        asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertTrue(snapshot.upcoming)
        self.assertEqual(snapshot.match_date, "2026-11-15")
        self.assertEqual(source.range_calls, 2)
        self.assertEqual(
            source.range_dates,
            [
                ("2026-11-02", "2026-11-12"),
                ("2026-11-12", "2026-11-22"),
            ],
        )

    def test_match_day_does_not_fetch_upcoming_range(self):
        source = FakeSource([FetchResult((match(),))])
        feed = service(source)
        asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertFalse(snapshot.upcoming)
        self.assertEqual(snapshot.match_date, "2026-11-01")
        self.assertEqual(source.range_calls, 0)

    def test_no_upcoming_matchday_keeps_empty_snapshot(self):
        source = FakeSource(
            [FetchResult(())], range_results=[FetchResult(())]
        )
        feed = service(source)
        asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertFalse(snapshot.upcoming)
        self.assertEqual(snapshot.matches, ())
        self.assertEqual(snapshot.match_date, "2026-11-01")
        self.assertEqual(source.range_calls, 2)

    def test_low_quota_skips_upcoming_range(self):
        source = FakeSource([FetchResult((), quota_remaining=1)])
        feed = service(source)
        asyncio.run(feed.refresh_once())

        self.assertEqual(source.range_calls, 0)
        self.assertFalse(feed.snapshot().upcoming)

    def test_upcoming_fetch_error_marks_feed_unavailable(self):
        source = FakeSource(
            [FetchResult(())],
            range_results=[HttpError("https://example.test/", status=429)],
        )
        feed = service(source)
        asyncio.run(feed.refresh_once())

        snapshot = feed.snapshot()
        self.assertIn("HTTP 429", snapshot.error)
        self.assertFalse(snapshot.has_value)

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
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0].kind, "GOAL")
        self.assertEqual(alerts[1].kind, "KO")
        self.assertEqual(alerts[0].home, "ARS")
        self.assertEqual(alerts[0].away, "CHE")
        self.assertEqual(alerts[0].home_goals, 2)
        self.assertEqual(alerts[0].away_goals, 0)
        self.assertEqual(alerts[0].minute, 40)
        self.assertEqual(alerts[0].competition, "PL")
        self.assertEqual(alerts[0].side, "home")

    def test_backfills_finished_match_history(self):
        finished = Match(
            id=1001,
            competition_id=2021,
            competition_code="PL",
            competition_name="PREMIER LEAGUE",
            home=Team(57, "ARSENAL", "ARS"),
            away=Team(61, "CHELSEA", "CHE"),
            kickoff=KICKOFF,
            status=MatchStatus.FINISHED,
            minute=90,
            home_goals=1,
            away_goals=1,
            goals=(
                Goal(23, None, 57, "ARSENAL", "SAKA",
                     home_score=1, away_score=0),
                Goal(67, None, 61, "CHELSEA", "PALMER",
                     home_score=1, away_score=1),
            ),
        )
        source = FakeSource([FetchResult((finished,))])
        feed = service(source)
        asyncio.run(feed.refresh_once())

        alerts = feed.snapshot().alerts
        self.assertEqual(
            [alert.kind for alert in alerts],
            ["FT", "GOAL", "HT", "GOAL", "KO"],
        )
        self.assertEqual(alerts[1].minute, 67)
        self.assertEqual(alerts[1].side, "away")
        self.assertEqual(alerts[3].minute, 23)
        self.assertEqual(alerts[3].side, "home")
        self.assertEqual(alerts[1].competition, "PL")
        self.assertEqual(alerts[-1].competition, "PL")

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
        self.assertEqual(alerts[0].home, "ARS")
        self.assertEqual(alerts[0].away, "CHE")
        self.assertEqual(alerts[0].home_goals, 2)
        self.assertEqual(alerts[0].away_goals, 0)

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
