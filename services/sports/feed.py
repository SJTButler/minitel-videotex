"""One shared poller and immutable snapshot for the football feed."""

import asyncio
import time
from contextlib import suppress
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from minitel.data.cache import ResourceCache, Snapshot
from minitel.data.http import HttpError
from minitel.data.services import service

from .config import SportsConfig
from .models import Alert, FeedSnapshot, MatchStatus
from .source import (
    FetchResult,
    FootballDataSource,
    local_date,
    local_today,
)

ALERT_LIMIT = 200
SOON_WINDOW = 6 * 3600
UPCOMING_WINDOW_DAYS = 10
UPCOMING_WINDOWS = 2


def _date_plus(value, days):
    return (date.fromisoformat(value) + timedelta(days=days)).isoformat()


def _next_matchday(matches, today):
    future = []
    for match in matches:
        match_date = local_date(match.kickoff)
        if match_date is not None and match_date > today:
            future.append((match_date, match))
    if not future:
        return None, ()
    next_date = min(match_date for match_date, _ in future)
    return next_date, tuple(
        match for match_date, match in future if match_date == next_date
    )


def _error_text(exc):
    if isinstance(exc, HttpError):
        if exc.status:
            return f"HTTP {exc.status} {exc.message}".strip()[:80]
        return (exc.message or "HTTP ERROR")[:80]
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    return (str(exc) or exc.__class__.__name__)[:80]


class SportsService:
    def __init__(self, config=None, source=None, clock=time.monotonic,
                 wall_clock=time.time, today=local_today,
                 thread_factory=None):
        self.config = config or SportsConfig.from_env()
        self.source = source
        if self.source is None and self.config.configured:
            self.source = FootballDataSource(
                self.config.token,
                base_url=self.config.base_url,
                competitions=self.config.competitions,
                timeout=self.config.timeout,
            )
        self.clock = clock
        self.wall_clock = wall_clock
        self.today = today
        self._snapshot = FeedSnapshot(loading=self.configured)
        self._alerts = []
        self._backfilled = False
        self._history_date = None
        self._task = None
        self.standings_cache = ResourceCache(
            ttl=86400,
            retry_delay=self.config.retry_delay,
            max_entries=max(1, len(self.config.competitions)),
            clock=clock,
            thread_factory=thread_factory,
        )

    @property
    def configured(self):
        return bool(self.config.configured and self.source is not None)

    @property
    def competitions(self):
        return self.config.competitions

    def snapshot(self):
        return self._snapshot

    def standings(self, code):
        if not self.configured:
            return Snapshot(error=RuntimeError("NOT CONFIGURED"))
        code = str(code).upper()
        return self.standings_cache.get(
            code, lambda: self.source.fetch_standings(code).value
        )

    async def start(self):
        if not self.configured or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="sports-feed")

    async def stop(self):
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _run(self):
        while True:
            try:
                delay = await self.refresh_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._fail(exc)
                delay = self._retry_delay(exc)
            await asyncio.sleep(delay)

    async def refresh_once(self):
        if not self.configured:
            return self.config.idle_interval
        self._snapshot = replace(self._snapshot, loading=True)
        today = self.today()
        try:
            result = await asyncio.to_thread(
                self.source.fetch_day, today
            )
            matches = tuple(result.value)
            match_date = today
            upcoming = False
            if not matches and (
                result.quota_remaining is None
                or result.quota_remaining > 1
            ):
                cursor = _date_plus(today, 1)
                for _ in range(UPCOMING_WINDOWS):
                    end = _date_plus(cursor, UPCOMING_WINDOW_DAYS)
                    upcoming_result = await asyncio.to_thread(
                        self.source.fetch_range, cursor, end
                    )
                    next_date, next_matches = _next_matchday(
                        upcoming_result.value, today
                    )
                    if next_date is not None:
                        matches = next_matches
                        match_date = next_date
                        upcoming = True
                        result = FetchResult(
                            matches,
                            quota_remaining=upcoming_result.quota_remaining,
                            quota_reset=upcoming_result.quota_reset,
                            goals_available=upcoming_result.goals_available,
                        )
                        break
                    cursor = end
        except Exception as exc:
            self._fail(exc)
            return self._retry_delay(exc)
        self._apply(result, match_date=match_date, upcoming=upcoming)
        return self.poll_delay()

    def _fail(self, exc):
        self._snapshot = replace(
            self._snapshot,
            loading=False,
            error=_error_text(exc),
        )

    def _retry_delay(self, exc):
        delay = self.config.retry_delay
        if isinstance(exc, HttpError) and exc.retry_after:
            delay = max(delay, float(exc.retry_after))
        return min(delay, 900.0)

    def _apply(self, result, *, match_date=None, upcoming=False):
        matches = tuple(result.value)
        now = datetime.now(timezone.utc)
        if upcoming:
            self._alerts = []
            self._backfilled = False
            self._history_date = None
        elif (
            not self._backfilled
            or match_date != self._history_date
            or not self._snapshot.matches
        ):
            self._alerts = []
            self._backfill_alerts(matches)
            self._backfilled = True
            self._history_date = match_date
        else:
            self._detect_alerts(matches, now)
        self._snapshot = FeedSnapshot(
            matches=matches,
            alerts=tuple(self._alerts),
            loaded_at=self.clock(),
            updated_at=self.wall_clock(),
            error=None,
            loading=False,
            quota_remaining=result.quota_remaining,
            quota_reset=result.quota_reset,
            goals_available=result.goals_available,
            match_date=match_date,
            upcoming=upcoming,
        )

    def _backfill_alerts(self, matches):
        events = []

        def add(match, at, order, kind, *, home_goals=None, away_goals=None,
                minute=None, injury_time=None):
            events.append(
                (
                    at,
                    order,
                    Alert(
                        at,
                        kind,
                        match.id,
                        match.home.short,
                        match.away.short,
                        home_goals,
                        away_goals,
                        minute,
                        injury_time,
                    ),
                )
            )

        for match in matches:
            if match.status not in (
                MatchStatus.LIVE,
                MatchStatus.HALF_TIME,
                MatchStatus.FINISHED,
            ):
                continue

            add(match, match.kickoff, 0, "KO")
            goal_times = []
            for goal in match.goals:
                minute = goal.minute or 0
                at = match.kickoff + timedelta(
                    minutes=minute + (goal.injury_time or 0)
                )
                goal_times.append(at)
                add(
                    match,
                    at,
                    1,
                    "GOAL",
                    home_goals=goal.home_score,
                    away_goals=goal.away_score,
                    minute=goal.minute,
                    injury_time=goal.injury_time,
                )

            if match.status is MatchStatus.HALF_TIME:
                add(
                    match,
                    match.kickoff + timedelta(minutes=45),
                    2,
                    "HT",
                    home_goals=match.home_goals,
                    away_goals=match.away_goals,
                )
            elif match.status is MatchStatus.FINISHED and match.goals:
                home_goals = 0
                away_goals = 0
                for goal in match.goals:
                    if (goal.minute or 0) <= 45:
                        if goal.home_score is not None:
                            home_goals = goal.home_score
                        if goal.away_score is not None:
                            away_goals = goal.away_score
                add(
                    match,
                    match.kickoff + timedelta(minutes=45),
                    2,
                    "HT",
                    home_goals=home_goals,
                    away_goals=away_goals,
                )

            if match.status is MatchStatus.FINISHED:
                last = max(
                    [match.kickoff + timedelta(minutes=90)] + goal_times
                )
                add(
                    match,
                    last + timedelta(minutes=1),
                    3,
                    "FT",
                    home_goals=match.home_goals,
                    away_goals=match.away_goals,
                )

        events.sort(key=lambda item: (item[0], item[1]))
        for _, _, alert in events:
            self._alert(alert)

    def _detect_alerts(self, matches, now):
        previous = {match.id: match for match in self._snapshot.matches}
        if not previous:
            return
        for match in matches:
            old = previous.get(match.id)
            if old is None:
                continue
            home = match.home.short
            away = match.away.short
            if (
                old.status is MatchStatus.SCHEDULED
                and match.status in (MatchStatus.LIVE, MatchStatus.HALF_TIME)
            ):
                self._alert(Alert(now, "KO", match.id, home, away))
            if (
                old.status is MatchStatus.LIVE
                and match.status is MatchStatus.HALF_TIME
            ):
                self._alert(
                    Alert(
                        now,
                        "HT",
                        match.id,
                        home,
                        away,
                        match.home_goals,
                        match.away_goals,
                    )
                )
            if (
                old.is_live or old.status is MatchStatus.SCHEDULED
            ) and match.status is MatchStatus.FINISHED:
                self._alert(
                    Alert(
                        now,
                        "FT",
                        match.id,
                        home,
                        away,
                        match.home_goals,
                        match.away_goals,
                    )
                )
            if (
                old.home_goals is not None
                and old.away_goals is not None
                and match.home_goals is not None
                and match.away_goals is not None
                and match.goal_total > old.goal_total
            ):
                self._alert(
                    Alert(
                        now,
                        "GOAL",
                        match.id,
                        home,
                        away,
                        match.home_goals,
                        match.away_goals,
                        match.minute,
                        match.injury_time,
                    )
                )

    def _alert(self, alert):
        key = (
            alert.match_id,
            alert.kind,
            alert.home,
            alert.away,
            alert.home_goals,
            alert.away_goals,
            alert.minute,
            alert.injury_time,
        )
        if any(
            (
                existing.match_id,
                existing.kind,
                existing.home,
                existing.away,
                existing.home_goals,
                existing.away_goals,
                existing.minute,
                existing.injury_time,
            )
            == key
            for existing in self._alerts
        ):
            return
        self._alerts.insert(0, alert)
        del self._alerts[ALERT_LIMIT:]

    def poll_delay(self, now=None):
        snapshot = self._snapshot
        if snapshot.error:
            return self.config.retry_delay
        if (
            snapshot.quota_remaining is not None
            and snapshot.quota_remaining <= 1
        ):
            return self.config.idle_interval
        if any(match.is_live for match in snapshot.matches):
            return self.config.live_interval
        if now is None:
            now = datetime.now(timezone.utc)
        upcoming = [
            match.kickoff for match in snapshot.matches
            if match.is_scheduled and match.kickoff > now
        ]
        if upcoming:
            soonest = min(upcoming)
            if (soonest - now).total_seconds() <= SOON_WINDOW:
                return self.config.day_interval
        return self.config.idle_interval


@service("sports", description="football-data.org")
def build_sports_service():
    return SportsService(config=SportsConfig.from_env())
