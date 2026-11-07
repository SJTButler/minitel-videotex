"""Page 151: match detail."""

from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit, wrap

from ..common.layout import ACCENT, SECONDARY, WARNING, key_footer, status
from ..common.widgets import page_input
from ._support.state import configured, find_match, find_matches, service, snapshot
from ._support.layout import (
    clock_label,
    day_label,
    goal_line,
    kickoff_label,
    minute_label,
    score_label,
)
from .live import DETAIL_PAGE, LIVE_PAGE
from services.sports.models import MatchStatus

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
    token = str(ctx.extension or "").strip().upper()
    if token:
        matches = find_matches(feed_snapshot, token)
    else:
        match = find_match(
            feed_snapshot, ctx.state.get("sports_match_id")
        )
        matches = (match,) if match is not None else ()

    s = Screen()
    status(s, f"PAGE 151#{ctx.extension}" if ctx.extension else "PAGE 151")
    s.text(1, 0, "MATCH", inverse=True, size=codec.DOUBLE_WIDTH)

    if not configured(feed):
        _message(s, ["SPORTS FEED NOT CONFIGURED", "SET FOOTBALL_API_KEY."])
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
        return s

    if not matches:
        if not token:
            lines = ["NO MATCH SELECTED.", "USE 151#TEAM OR 151#HOMEAWAY."]
        elif feed_snapshot is not None and feed_snapshot.error:
            lines = ["MATCH DATA UNAVAILABLE.", "RETURN TO LIVE SCORES."]
        elif feed_snapshot is None or not feed_snapshot.has_value:
            lines = ["MATCH DATA LOADING...", "TRY AGAIN IN A MOMENT."]
        else:
            lines = [f"NO MATCH FOR {token}.", "CHECK LIVE SCORES."]
        _message(s, lines)
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
        return s

    if len(matches) > 1:
        s.text(
            4,
            0,
            fit(f"MULTIPLE MATCHES FOR {token}", codec.COLS),
            fg=WARNING,
        )
        for index, candidate in enumerate(matches[:12]):
            code = f"{candidate.home.short}{candidate.away.short}"
            s.text(
                5 + index,
                0,
                fit(
                    f"{candidate.home.short} V {candidate.away.short}"
                    f"  151#{code}",
                    codec.COLS,
                ),
                fg=SECONDARY,
            )
        if len(matches) > 12:
            s.text(
                18,
                0,
                f"+{len(matches) - 12} MORE MATCHES",
                fg=SECONDARY,
            )
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
        return s

    match = matches[0]

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
    requires=("sports",),
    back_page=LIVE_PAGE,
    extension_back_page=LIVE_PAGE,
    tick_interval=5.0,
    on_tick=detail_screen,
    extensions=True,
)
def match_detail(ctx):
    return detail_screen(ctx)
