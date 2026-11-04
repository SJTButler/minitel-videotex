"""football-data.org sports background service."""

from .config import SportsConfig
from .feed import SportsService, build_sports_service
from .models import (
    Alert,
    FeedSnapshot,
    Goal,
    Match,
    MatchStatus,
    StandingRow,
    Team,
)
from .source import FootballDataSource, local_date, local_today

__all__ = [
    "Alert",
    "FeedSnapshot",
    "FootballDataSource",
    "Goal",
    "Match",
    "MatchStatus",
    "SportsConfig",
    "SportsService",
    "StandingRow",
    "Team",
    "build_sports_service",
    "local_date",
    "local_today",
]
