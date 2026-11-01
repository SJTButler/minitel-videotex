"""Page 150: live scores by league, grouped by kickoff time."""

from dataclasses import dataclass

from minitel import Carousel, codec
from minitel.pages import page
from minitel.screen import Screen
from minitel.text import fit, sanitize

from ..layout import (
    ACCENT,
    SECONDARY,
    WARNING,
    key_footer,
    page_input,
    status,
)
from .common import clear_error, configured, service, set_error, snapshot
from .layout import (
    clock_label,
    kickoff_label,
    match_sort_key,
    minute_label,
    score_label,
)
from services.sports.models import FeedSnapshot, MatchStatus

LIVE_PAGE = "150"
DETAIL_PAGE = "151"
SCORE_TOP = 4
SCORE_ROWS = 11
COLUMN_WIDTH = 20
MAX_MATCHES = SCORE_ROWS * 2
ALERT_ROWS = 2


@dataclass(frozen=True)
class ScoreRow:
    label: str = ""
    left: object = None
    right: object = None


@dataclass(frozen=True)
class LeaguePage:
    code: str
    number: int
    count: int
    rows: tuple
    matches: tuple


def _matches(feed_snapshot):
    return tuple(sorted(feed_snapshot.matches, key=match_sort_key))


def _league_pages(code, matches):
    groups = {}
    for match in matches:
        groups.setdefault(kickoff_label(match.kickoff), []).append(match)

    ordered = sorted(
        groups.items(),
        key=lambda item: min(match.kickoff for match in item[1]),
    )
    pages = []
    current = []
    for label, group in ordered:
        group.sort(key=lambda match: (
            match.home.name, match.away.name, match.id
        ))
        pairs = [group[index:index + 2] for index in range(0, len(group), 2)]
        chunk_size = SCORE_ROWS - 1
        chunks = [
            pairs[index:index + chunk_size]
            for index in range(0, len(pairs), chunk_size)
        ]
        for chunk in chunks:
            needed = 1 + len(chunk)
            if len(current) + needed > SCORE_ROWS:
                if current:
                    pages.append(current)
                current = []
            current.append(ScoreRow(label=label))
            for pair in chunk:
                current.append(
                    ScoreRow(
                        left=pair[0],
                        right=pair[1] if len(pair) > 1 else None,
                    )
                )
    if current:
        pages.append(current)
    return pages


def _pages(feed, matches):
    if not matches:
        return ()
    present = {match.competition_code for match in matches}
    order = []
    configured_codes = (
        tuple(getattr(feed, "competitions", ())) if feed is not None else ()
    )
    for code in configured_codes:
        if code in present and code not in order:
            order.append(code)
    for code in sorted(present - set(order)):
        order.append(code)

    pages = []
    for code in order:
        league = [
            match for match in matches if match.competition_code == code
        ]
        league_pages = _league_pages(code, league)
        total = len(league_pages)
        for index, rows in enumerate(league_pages):
            display = []
            for row in rows:
                if row.left is not None:
                    display.append(row.left)
                if row.right is not None:
                    display.append(row.right)
            pages.append(
                LeaguePage(
                    code=code,
                    number=index + 1,
                    count=total,
                    rows=tuple(rows),
                    matches=tuple(display),
                )
            )
    return tuple(pages)


def _score_pager(ctx, pages):
    return ctx.set_pager(
        len(pages),
        1,
        carousel=Carousel(hold=30.0, wrap=True),
    )


def _current_page(pager, pages):
    window = pager.window(pages)
    return window[0] if window else None


def _competition_name(feed, code):
    if feed is not None and hasattr(feed, "competition_name"):
        return feed.competition_name(code)
    return code


def _header(feed, feed_snapshot, page):
    if not configured(feed):
        return "SPORTS FEED NOT CONFIGURED"
    if feed_snapshot.error and not feed_snapshot.has_value:
        return "SCORES UNAVAILABLE."
    if not feed_snapshot.has_value:
        return "LOADING MATCHES..."
    if page is None:
        return "NO MATCHES TODAY."
    name = _competition_name(feed, page.code)
    if feed_snapshot.error:
        return fit(
            f"{name}  DATA STALE  UPD "
            f"{clock_label(feed_snapshot.updated_at)}",
            codec.COLS,
        )
    live = sum(1 for match in page.matches if match.is_live)
    return fit(
        f"{name}  LIVE {live}  UPD "
        f"{clock_label(feed_snapshot.updated_at)}",
        codec.COLS,
    )


def _header_colour(feed, feed_snapshot):
    if not configured(feed) or feed_snapshot.error:
        return WARNING
    return SECONDARY


def _empty_lines(feed, feed_snapshot):
    if not configured(feed):
        return ["SPORTS FEED NOT CONFIGURED", "SET FOOTBALL_API_KEY."]
    if feed_snapshot.error and not feed_snapshot.has_value:
        return ["SCORES UNAVAILABLE.", "CHECK CONNECTION. RETRYING."]
    if not feed_snapshot.has_value:
        return ["LOADING MATCHES..."]
    return ["NO MATCHES TODAY.", "CHECK BACK ON MATCHDAY."]


def _hint(ctx, feed, feed_snapshot, window):
    error = ctx.state.get("sports_error")
    if error:
        return error
    if not configured(feed):
        return "SET FOOTBALL_API_KEY."
    if feed_snapshot.error and feed_snapshot.matches:
        return "DATA STALE. RETRYING."
    if feed_snapshot.error and not feed_snapshot.has_value:
        return "SCORES UNAVAILABLE. RETRYING."
    if not feed_snapshot.has_value:
        return "LOADING MATCHES..."
    if not window:
        return "NO MATCHES TODAY."
    return f"TYPE 1-{len(window)}, THEN ENVOI"


def _status_suffix(match):
    if match.is_live:
        return f"{minute_label(match):<5}"
    if match.is_finished:
        return "FT   "
    if match.status is MatchStatus.POSTPONED:
        return "PST  "
    if match.status is MatchStatus.CANCELLED:
        return "CAN  "
    return "     "


def _cell(match, number):
    return f"{number:>2} {match.home.short:<3} {score_label(match):>3} " \
           f"{match.away.short:<3} {_status_suffix(match)}"


def _draw_cell(s, row, col, match, number):
    suffix = _status_suffix(match)
    s.text(row, col, fit(_cell(match, number), COLUMN_WIDTH))
    if suffix.strip():
        colour = ACCENT if match.is_live else SECONDARY
        s.text(row, col + 15, suffix, fg=colour)


def live_screen(ctx):
    feed = service(ctx)
    feed_snapshot = snapshot(ctx) if feed is not None else FeedSnapshot(
        error="NOT CONFIGURED"
    )
    matches = _matches(feed_snapshot) if configured(feed) else ()
    pages = _pages(feed, matches)
    pager = _score_pager(ctx, pages)
    page = _current_page(pager, pages)
    window = page.matches if page is not None else ()

    if (
        ctx.state.get("sports_error")
        and ctx.state.get("sports_error_offset") != pager.offset
    ):
        clear_error(ctx)

    s = Screen()
    status(s, f"150 {pager.label}" if pager.total else "150")
    title = f"LIVE SCORES - {page.code}" if page is not None else "LIVE SCORES"
    if page is not None and page.count > 1:
        title += f" {page.number}/{page.count}"
    s.text(
        1,
        0,
        fit(title, codec.COLS // 2),
        inverse=True,
        size=codec.DOUBLE_WIDTH,
    )
    s.text(
        2,
        0,
        _header(feed, feed_snapshot, page),
        fg=_header_colour(feed, feed_snapshot),
    )
    s.rule(3, 0, codec.COLS, "-")

    if page is not None and page.rows:
        number = 1
        for index, item in enumerate(page.rows):
            row = SCORE_TOP + index
            if item.label:
                s.text(row, 0, item.label, fg=ACCENT, underline=True)
                continue
            if item.left is not None:
                _draw_cell(s, row, 0, item.left, number)
                number += 1
            if item.right is not None:
                _draw_cell(s, row, COLUMN_WIDTH, item.right, number)
                number += 1
    else:
        colour = _header_colour(feed, feed_snapshot)
        for index, line in enumerate(_empty_lines(feed, feed_snapshot)):
            s.text(SCORE_TOP + index, 0, fit(line, codec.COLS), fg=colour)

    s.rule(15, 0, codec.COLS, "-")
    s.fill(16, 0, codec.COLS, " ", inverse=True)
    s.text(16, 0, "VIDIPRINTER", inverse=True)

    alerts = feed_snapshot.alerts[:ALERT_ROWS] if configured(feed) else ()
    if alerts:
        for index, alert in enumerate(alerts):
            s.text(17 + index, 0, fit(alert.text, codec.COLS))
    else:
        live = any(match.is_live for match in feed_snapshot.matches)
        note = "WATCHING FOR GOALS" if live else "WAITING FOR KICKOFF"
        s.text(17, 0, note, fg=SECONDARY)

    waning = (
        not configured(feed)
        or feed_snapshot.error
        or ctx.state.get("sports_error")
    )
    s.text(
        19,
        0,
        fit(_hint(ctx, feed, feed_snapshot, window), codec.COLS),
        fg=WARNING if waning else SECONDARY,
    )
    page_input(s, ctx, cursor="auto")
    key_footer(s, ("SUITE=NEXT", "RETOUR=BACK", "SOMMAIRE=HOME"))
    s.text(23, 0, "153=TABLES  154=STATUS", fg=SECONDARY)
    return s


def submit_live(ctx, line):
    value = line.strip()
    feed = service(ctx)
    feed_snapshot = snapshot(ctx) if feed is not None else FeedSnapshot(
        error="NOT CONFIGURED"
    )
    matches = _matches(feed_snapshot) if configured(feed) else ()
    pages = _pages(feed, matches)
    pager = _score_pager(ctx, pages)
    page = _current_page(pager, pages)
    window = page.matches if page is not None else ()

    if value.isdigit() and 1 <= int(value) <= MAX_MATCHES:
        number = int(value)
        if number <= len(window):
            ctx.state["sports_match_id"] = window[number - 1].id
            clear_error(ctx)
            return DETAIL_PAGE
        set_error(ctx, f"NO MATCH {number}.", pager.offset)
        ctx.values["input"] = ""
        return LIVE_PAGE

    if ctx.page_for(value) is not None:
        clear_error(ctx)
        return None

    set_error(
        ctx,
        fit(f"NO MATCH {sanitize(value)}.", codec.COLS),
        pager.offset,
    )
    ctx.values["input"] = ""
    return LIVE_PAGE


@page(
    LIVE_PAGE,
    title="LIVE SCORES",
    aliases=("5",),
    requires=("sports",),
    tick_interval=5.0,
    on_submit=submit_live,
    on_tick=live_screen,
    no_screensaver=True,
)
def live_scores(ctx):
    return live_screen(ctx)
