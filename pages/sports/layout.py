"""Formatting helpers shared by the sports pages."""

import time
from datetime import timezone

from minitel.text import fit

from services.sports.models import MatchStatus

try:
    from zoneinfo import ZoneInfo

    LOCAL_ZONE = ZoneInfo("Europe/London")
except (ImportError, KeyError):
    LOCAL_ZONE = None


def local_time(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if LOCAL_ZONE is not None:
        return value.astimezone(LOCAL_ZONE)
    return value.astimezone()


def kickoff_label(value):
    local = local_time(value)
    return local.strftime("%H:%M") if local else "--:--"


def day_label(value):
    local = local_time(value)
    return local.strftime("%a %d %b").upper() if local else "--- -- ---"


def clock_label(timestamp):
    if timestamp is None:
        return "--:--:--"
    try:
        return time.strftime("%H:%M:%S", time.localtime(timestamp))
    except (OSError, OverflowError, ValueError):
        return "--:--:--"


def minute_label(match):
    if match.status is MatchStatus.HALF_TIME:
        return "HT"
    if match.status is MatchStatus.FINISHED:
        return "FT"
    if match.status is MatchStatus.POSTPONED:
        return "PST"
    if match.status is MatchStatus.CANCELLED:
        return "CAN"
    if match.status is MatchStatus.SCHEDULED:
        return kickoff_label(match.kickoff)
    if match.status is MatchStatus.LIVE:
        if match.minute is None:
            return "LIVE"
        if match.injury_time:
            return f"{match.minute}+{match.injury_time}'"
        return f"{match.minute}'"
    return "?"


def score_label(match):
    if match.home_goals is None or match.away_goals is None:
        if match.status is MatchStatus.SCHEDULED:
            return "v"
        return "-"
    return f"{match.home_goals}-{match.away_goals}"


def match_row(match, number=None):
    lead = str(number) if number is not None else " "
    return fit(
        f"{lead} {match.home.short:<3} {score_label(match):>3} "
        f"{match.away.short:<3} {minute_label(match):<5} "
        f"{match.competition_code:<3}",
        40,
    )


def match_sort_key(match):
    if match.is_live:
        rank = 0
    elif match.is_scheduled:
        rank = 1
    else:
        rank = 2
    return (rank, match.kickoff, match.competition_code, match.id)


def goal_line(match, goal):
    if goal.minute is None:
        minute = ""
    elif goal.injury_time:
        minute = f"{goal.minute}+{goal.injury_time}'"
    else:
        minute = f"{goal.minute}'"
    if goal.team_id is not None and goal.team_id == match.home.id:
        team = match.home.short
    elif goal.team_id is not None and goal.team_id == match.away.id:
        team = match.away.short
    else:
        team = goal.team_name[:3]
    marker = ""
    if goal.own_goal:
        marker = " (OG)"
    elif goal.penalty:
        marker = " (P)"
    score = ""
    if goal.home_score is not None and goal.away_score is not None:
        score = f" {goal.home_score}-{goal.away_score}"
    scorer = goal.scorer or "GOAL"
    return fit(f"{minute:<5}{team:<4}{scorer}{marker}{score}", 40)


def table_header():
    return f"{'':>2} {'TEAM':<16} {'PL':>2} {'GD':>4} {'PTS':>3}"


def table_row(row):
    difference = row.goal_difference
    gd = f"+{difference}" if difference > 0 else str(difference)
    return fit(
        f"{row.position:>2} {row.team.name[:16]:<16} "
        f"{row.played:>2} {gd:>4} {row.points:>3}",
        40,
    )
