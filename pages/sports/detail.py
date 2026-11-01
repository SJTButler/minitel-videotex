"""Page 151: match detail."""

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen
from minitel.text import fit, wrap

from ..layout import ACCENT, SECONDARY, WARNING, key_footer, page_input, status
from .common import configured, find_match, service, snapshot
from .layout import (
    clock_label,
    day_label,
    goal_line,
    kickoff_label,
    minute_label,
    score_label,
)
from .live import DETAIL_PAGE, LIVE_PAGE
from .models import MatchStatus

GOAL_ROWS = 6


def _message(s, lines, colour=WARNING):
    for index, line in enumerate(lines):
        s.text(4 + index, 0, fit(line, codec.COLS), fg=colour)


def _fixture_lines(match):
    home = wrap(match.home.name, codec.COLS, max_lines=2)
    away = wrap(match.away.name, codec.COLS, max_lines=2)
    return home, away


def detail_screen(ctx):
    feed = service(ctx)
    feed_snapshot = snapshot(ctx) if feed is not None else None
    match = find_match(feed_snapshot, ctx.state.get("sports_match_id"))

    s = Screen()
    status(s, "PAGE 151")
    s.text(1, 0, "MATCH", inverse=True, size=codec.DOUBLE_WIDTH)

    if not configured(feed):
        _message(s, ["SPORTS FEED NOT CONFIGURED", "SET FOOTBALL_API_KEY."])
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
        return s

    if ctx.state.get("sports_match_id") is None:
        _message(s, ["NO MATCH SELECTED.", "OPEN LIVE SCORES, PICK A NUMBER."])
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
        return s

    if match is None:
        if feed_snapshot is not None and feed_snapshot.error:
            lines = ["MATCH DATA UNAVAILABLE.", "RETURN TO LIVE SCORES."]
        elif feed_snapshot is None or not feed_snapshot.has_value:
            lines = ["MATCH DATA LOADING...", "TRY AGAIN IN A MOMENT."]
        else:
            lines = ["MATCH NOT AVAILABLE.", "RETURN TO LIVE SCORES."]
        _message(s, lines)
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
        return s

    competition = fit(match.competition_name, 30)
    if match.matchday is not None:
        competition = fit(f"{competition}  MATCHDAY {match.matchday}", 40)
    s.text(2, 0, competition, fg=SECONDARY)

    status_text = (
        "KICKOFF"
        if match.status is MatchStatus.SCHEDULED
        else minute_label(match)
    )
    line = (
        f"{day_label(match.kickoff)} {kickoff_label(match.kickoff)}  "
        f"{status_text}"
    )
    s.text(
        3,
        0,
        fit(line, codec.COLS),
        fg=WARNING if feed_snapshot.error else SECONDARY,
    )

    home_lines, away_lines = _fixture_lines(match)
    for index, text in enumerate(home_lines):
        s.text(5 + index, 0, text)
    s.text(
        7,
        0,
        score_label(match),
        fg=SECONDARY if match.status is MatchStatus.FINISHED else ACCENT,
        size=codec.DOUBLE_WIDTH,
    )
    for index, text in enumerate(away_lines):
        s.text(9 + index, 0, text)

    if match.goals:
        s.rule(11, 0, codec.COLS, "-")
        s.fill(12, 0, codec.COLS, " ", inverse=True)
        s.text(12, 0, "GOALS", inverse=True)
        for index, goal in enumerate(match.goals[:GOAL_ROWS]):
            s.text(13 + index, 0, goal_line(match, goal))
        hidden = len(match.goals) - GOAL_ROWS
        if hidden > 0:
            s.text(
                13 + GOAL_ROWS,
                0,
                fit(f"+{hidden} MORE GOALS", codec.COLS),
                fg=SECONDARY,
            )
    elif match.goal_total > 0:
        if feed_snapshot.goals_available is False:
            note = "GOAL EVENTS NOT IN YOUR PLAN."
        elif feed_snapshot.goals_available is True:
            note = "GOAL EVENTS UNAVAILABLE."
        else:
            note = "NO GOAL DATA."
        s.text(11, 0, fit(note, codec.COLS), fg=SECONDARY)

    updated = f"UPDATED {clock_label(feed_snapshot.updated_at)}"
    s.text(23, 0, fit(updated, codec.COLS), fg=SECONDARY)
    page_input(s, ctx, cursor="auto")
    key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
    return s


@page(
    DETAIL_PAGE,
    title="MATCH",
    back_page=LIVE_PAGE,
    tick_interval=5.0,
    on_tick=detail_screen,
    no_screensaver=True,
)
def match_detail(ctx):
    return detail_screen(ctx)
