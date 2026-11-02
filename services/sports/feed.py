"""One shared poller and immutable snapshot for the football feed."""

import asyncio
import time
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timezone

from minitel.cache import ResourceCache, Snapshot
from minitel.http import HttpError
from minitel.services import service

from .config import SportsConfig
from .models import Alert, FeedSnapshot, MatchStatus
from .source import FootballDataSource, local_today

ALERT_LIMIT = 20
SOON_WINDOW = 6 * 3600


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
                 wall_clock=time.time, thread_factory=None):
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
        self._snapshot = FeedSnapshot(loading=self.configured)
        self._alerts = []
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
        try:
            result = await asyncio.to_thread(
                self.source.fetch_day, local_today()
            )
        except Exception as exc:
            self._fail(exc)
            return self._retry_delay(exc)
        self._apply(result)
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

    def _apply(self, result):
        matches = tuple(result.value)
        now = datetime.now(timezone.utc)
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
        )

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
