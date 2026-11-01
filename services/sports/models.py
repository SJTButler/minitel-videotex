"""Provider-neutral sports models."""

import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MatchStatus(Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    HALF_TIME = "HALF_TIME"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Team:
    id: int | None
    name: str
    short: str


@dataclass(frozen=True)
class Goal:
    minute: int | None
    injury_time: int | None
    team_id: int | None
    team_name: str
    scorer: str
    own_goal: bool = False
    penalty: bool = False
    home_score: int | None = None
    away_score: int | None = None


@dataclass(frozen=True)
class Match:
    id: int
    competition_id: int | None
    competition_code: str
    competition_name: str
    home: Team
    away: Team
    kickoff: datetime
    status: MatchStatus
    minute: int | None = None
    injury_time: int | None = None
    home_goals: int | None = None
    away_goals: int | None = None
    goals: tuple[Goal, ...] = ()
    matchday: int | None = None
    venue: str = ""

    @property
    def is_live(self):
        return self.status in (MatchStatus.LIVE, MatchStatus.HALF_TIME)

    @property
    def is_scheduled(self):
        return self.status is MatchStatus.SCHEDULED

    @property
    def is_finished(self):
        return self.status is MatchStatus.FINISHED

    @property
    def goal_total(self):
        return (self.home_goals or 0) + (self.away_goals or 0)


@dataclass(frozen=True)
class StandingRow:
    position: int
    team: Team
    played: int
    goal_difference: int
    points: int


@dataclass(frozen=True)
class Alert:
    at: datetime
    kind: str
    match_id: int
    text: str


@dataclass(frozen=True)
class FeedSnapshot:
    matches: tuple[Match, ...] = ()
    alerts: tuple[Alert, ...] = ()
    loaded_at: float | None = None
    updated_at: float | None = None
    error: str | None = None
    loading: bool = False
    quota_remaining: int | None = None
    quota_reset: int | None = None
    goals_available: bool | None = None

    @property
    def has_value(self):
        return self.loaded_at is not None

    def age(self, now=None):
        if self.loaded_at is None:
            return None
        if now is None:
            now = time.monotonic()
        return max(0.0, now - self.loaded_at)


COMPETITION_NAMES = {
    "PL": "PREMIER LEAGUE",
    "PD": "LA LIGA",
    "BL1": "BUNDESLIGA",
    "SA": "SERIE A",
    "FL1": "LIGUE 1",
    "CL": "CHAMPIONS LEAGUE",
    "ELC": "CHAMPIONSHIP",
    "EL1": "LEAGUE ONE",
    "EL2": "LEAGUE TWO",
    "DED": "EREDIVISIE",
    "PPL": "PRIMEIRA LIGA",
    "BSA": "BRASIL SERIE A",
    "WC": "WORLD CUP",
    "EC": "EUROPEAN CHAMPIONSHIP",
}


def competition_name(code):
    return COMPETITION_NAMES.get(code.upper(), code.upper())
