"""football-data.org v4 parsing and HTTP source."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from minitel.data.http import get_json_response
from minitel.text import sanitize

from .config import DEFAULT_BASE_URL, DEFAULT_COMPETITIONS
from .models import (
    Goal,
    Match,
    MatchStatus,
    StandingRow,
    Team,
)

try:
    from zoneinfo import ZoneInfo

    LOCAL_ZONE = ZoneInfo("Europe/London")
except (ImportError, KeyError):
    LOCAL_ZONE = None

_STATUS = {
    "SCHEDULED": MatchStatus.SCHEDULED,
    "TIMED": MatchStatus.SCHEDULED,
    "IN_PLAY": MatchStatus.LIVE,
    "PAUSED": MatchStatus.HALF_TIME,
    "EXTRA_TIME": MatchStatus.LIVE,
    "PENALTY_SHOOTOUT": MatchStatus.LIVE,
    "FINISHED": MatchStatus.FINISHED,
    "AWARDED": MatchStatus.FINISHED,
    "SUSPENDED": MatchStatus.POSTPONED,
    "POSTPONED": MatchStatus.POSTPONED,
    "CANCELLED": MatchStatus.CANCELLED,
}

_CLUB_AFFIXES = {
    "FC", "AFC", "CF", "SC", "AC", "CLUB", "REAL", "DE", "THE", "CALCIO",
    "AS", "US", "SS", "SSC", "RC", "RCD", "UD", "CD", "CA", "EC", "SE",
}


@dataclass(frozen=True)
class FetchResult:
    value: tuple
    quota_remaining: int | None = None
    quota_reset: int | None = None
    goals_available: bool | None = None


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _header(headers, name):
    if not headers:
        return None
    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return value
    return None


def _quota(headers):
    remaining = _header(headers, "X-RequestsAvailable")
    if remaining is None:
        remaining = _header(headers, "x-requests-available-minute")
    if remaining is None:
        remaining = _header(headers, "X-Requests-Available-Minute")
    return (
        _as_int(remaining),
        _as_int(_header(headers, "X-RequestCounter-Reset")),
    )


def _parse_utc(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def local_date(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if LOCAL_ZONE is not None:
        value = value.astimezone(LOCAL_ZONE)
    return value.date().isoformat()


def local_today():
    return local_date(datetime.now(timezone.utc))


def _team_short(raw, name):
    tla = sanitize(raw.get("tla") or "")
    if tla:
        return tla[:3]
    tokens = [
        token for token in re.findall(r"[A-Z0-9]+", name)
        if token not in _CLUB_AFFIXES
    ]
    if not tokens:
        return "???"
    if len(tokens) >= 2:
        return (tokens[0][0] + tokens[1][0] + tokens[-1][0])[:3]
    return tokens[0][:3]


def parse_team(raw):
    if not isinstance(raw, dict):
        return None
    name = sanitize(raw.get("name") or raw.get("shortName") or "")
    if not name:
        return None
    return Team(
        id=_as_int(raw.get("id")),
        name=name,
        short=_team_short(raw, name),
    )


def parse_status(value):
    return _STATUS.get(str(value or "").upper(), MatchStatus.UNKNOWN)


def parse_score(raw):
    score = raw if isinstance(raw, dict) else {}
    full = score.get("fullTime")
    if not isinstance(full, dict):
        full = {}
    home = _as_int(full.get("home"))
    away = _as_int(full.get("away"))
    if home is None and away is None:
        half = score.get("halfTime")
        if isinstance(half, dict):
            home = _as_int(half.get("home"))
            away = _as_int(half.get("away"))
    return home, away


def parse_goals(raw):
    goals = raw.get("goals") if isinstance(raw, dict) else None
    if not isinstance(goals, (list, tuple)):
        return ()
    parsed = []
    for goal in goals:
        if not isinstance(goal, dict):
            continue
        team = goal.get("team")
        if not isinstance(team, dict):
            team = {}
        scorer = goal.get("scorer")
        if not isinstance(scorer, dict):
            scorer = {}
        score = goal.get("score")
        if not isinstance(score, dict):
            score = {}
        kind = str(goal.get("type") or "").upper()
        parsed.append(
            Goal(
                minute=_as_int(goal.get("minute")),
                injury_time=_as_int(goal.get("injuryTime")),
                team_id=_as_int(team.get("id")),
                team_name=sanitize(team.get("name") or ""),
                scorer=sanitize(scorer.get("name") or ""),
                own_goal=kind == "OWN",
                penalty=kind == "PENALTY",
                home_score=_as_int(score.get("home")),
                away_score=_as_int(score.get("away")),
            )
        )
    parsed.sort(
        key=lambda goal: (goal.minute or 0, goal.injury_time or 0)
    )
    return tuple(parsed)


def goals_available(payload):
    """Whether the provider included goal events in this match list."""
    if isinstance(payload, dict):
        raw_matches = payload.get("matches")
    elif isinstance(payload, (list, tuple)):
        raw_matches = payload
    else:
        return None
    if not isinstance(raw_matches, (list, tuple)) or not raw_matches:
        return None
    return any(
        isinstance(match, dict) and "goals" in match
        for match in raw_matches
    )


def parse_matches(payload, competitions=None):
    if isinstance(payload, dict):
        raw_matches = payload.get("matches")
    elif isinstance(payload, (list, tuple)):
        raw_matches = payload
    else:
        raw_matches = None
    if not isinstance(raw_matches, (list, tuple)):
        return ()

    allowed = None
    if competitions:
        allowed = {str(code).upper() for code in competitions}

    matches = []
    for raw in raw_matches:
        if not isinstance(raw, dict):
            continue
        competition = raw.get("competition")
        if not isinstance(competition, dict):
            competition = {}
        code = sanitize(competition.get("code") or "")
        if allowed is not None and code not in allowed:
            continue
        match_id = _as_int(raw.get("id"))
        kickoff = _parse_utc(raw.get("utcDate"))
        home = parse_team(raw.get("homeTeam"))
        away = parse_team(raw.get("awayTeam"))
        if match_id is None or kickoff is None or home is None or away is None:
            continue
        home_goals, away_goals = parse_score(raw.get("score"))
        matches.append(
            Match(
                id=match_id,
                competition_id=_as_int(competition.get("id")),
                competition_code=code,
                competition_name=sanitize(competition.get("name") or code),
                home=home,
                away=away,
                kickoff=kickoff,
                status=parse_status(raw.get("status")),
                minute=_as_int(raw.get("minute")),
                injury_time=_as_int(raw.get("injuryTime")),
                home_goals=home_goals,
                away_goals=away_goals,
                goals=parse_goals(raw),
                matchday=_as_int(raw.get("matchday")),
                venue=sanitize(raw.get("venue") or ""),
            )
        )
    matches.sort(key=lambda match: (
        match.kickoff, match.competition_code, match.id
    ))
    return tuple(matches)


def parse_standings(payload):
    if not isinstance(payload, dict):
        return ()
    standings = payload.get("standings")
    if not isinstance(standings, (list, tuple)):
        return ()
    selected = None
    for table in standings:
        if isinstance(table, dict) and table.get("type") == "TOTAL":
            selected = table
            break
    if selected is None:
        selected = next(
            (table for table in standings if isinstance(table, dict)), None
        )
    if selected is None:
        return ()
    rows = selected.get("table")
    if not isinstance(rows, (list, tuple)):
        return ()

    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        team = parse_team(row.get("team"))
        if team is None:
            continue
        parsed.append(
            StandingRow(
                position=_as_int(row.get("position")) or 0,
                team=team,
                played=_as_int(row.get("playedGames")) or 0,
                goal_difference=_as_int(row.get("goalDifference")) or 0,
                points=_as_int(row.get("points")) or 0,
            )
        )
    parsed.sort(key=lambda row: (row.position, row.team.name))
    return tuple(parsed)


class FootballDataSource:
    def __init__(self, token, *, base_url=DEFAULT_BASE_URL,
                 competitions=DEFAULT_COMPETITIONS,
                 get_json_response=get_json_response, timeout=10.0):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.competitions = tuple(
            str(code).upper() for code in competitions
        )
        self._get_json_response = get_json_response
        self.timeout = timeout

    def _get(self, url, *, unfold_goals=False):
        headers = {"X-Auth-Token": self.token}
        if unfold_goals:
            headers["X-Unfold-Goals"] = "true"
        return self._get_json_response(
            url, headers=headers, timeout=self.timeout
        )

    def _fetch_matches(self, url):
        response = self._get(url, unfold_goals=True)
        quota_remaining, quota_reset = _quota(response.headers)
        return FetchResult(
            parse_matches(response.payload, self.competitions),
            quota_remaining=quota_remaining,
            quota_reset=quota_reset,
            goals_available=goals_available(response.payload),
        )

    def fetch_day(self, date=None):
        day = date or local_today()
        codes = quote(",".join(self.competitions), safe=",")
        url = (
            f"{self.base_url}/matches?date={quote(str(day))}"
            f"&competitions={codes}"
        )
        return self._fetch_matches(url)

    def fetch_range(self, start, end):
        codes = quote(",".join(self.competitions), safe=",")
        url = (
            f"{self.base_url}/matches?dateFrom={quote(str(start))}"
            f"&dateTo={quote(str(end))}&competitions={codes}"
        )
        return self._fetch_matches(url)

    def fetch_standings(self, code):
        url = f"{self.base_url}/competitions/{quote(str(code))}/standings"
        response = self._get(url)
        quota_remaining, quota_reset = _quota(response.headers)
        return FetchResult(
            parse_standings(response.payload),
            quota_remaining=quota_remaining,
            quota_reset=quota_reset,
        )
