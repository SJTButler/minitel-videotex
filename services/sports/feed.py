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
from .models import Alert, FeedSnapshot, MatchStatus, competition_name
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


def _minute_text(match):
    if match.minute is None:
        return ""
    if match.injury_time:
        return f"{match.minute}+{match.injury_time}'"
    return f"{match.minute}'"


def _score_text(match):
    if match.home_goals is None or match.away_goals is None:
        return "V"
    return f"{match.home_goals}-{match.away_goals}"


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

    def competition_name(self, code):
        return competition_name(code)

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
            score = _score_text(match)
            if (
                old.status is MatchStatus.SCHEDULED
                and match.status in (MatchStatus.LIVE, MatchStatus.HALF_TIME)
            ):
                self._alert(match, "KO", f"KO {home} V {away}", now)
            if (
                old.status is MatchStatus.LIVE
                and match.status is MatchStatus.HALF_TIME
            ):
                self._alert(match, "HT", f"HT {home} {score} {away}", now)
            if (
                old.is_live or old.status is MatchStatus.SCHEDULED
            ) and match.status is MatchStatus.FINISHED:
                self._alert(match, "FT", f"FT {home} {score} {away}", now)
            if (
                old.home_goals is not None
                and old.away_goals is not None
                and match.home_goals is not None
                and match.away_goals is not None
                and match.goal_total > old.goal_total
            ):
                minute = _minute_text(match)
                suffix = f" {minute}" if minute else ""
                self._alert(
                    match,
                    "GOAL",
                    f"GOAL {home} {score} {away}{suffix}",
                    now,
                )

    def _alert(self, match, kind, text, now):
        if any(
            alert.match_id == match.id
            and alert.kind == kind
            and alert.text == text
            for alert in self._alerts
        ):
            return
        self._alerts.insert(0, Alert(now, kind, match.id, text))
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
