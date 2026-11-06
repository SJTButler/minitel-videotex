"""Page 150: live scores or next fixtures by league."""

from minitel.protocol import codec
from minitel.design import Carousel
from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit, sanitize

from ..common.layout import (
    SECONDARY,
    WARNING,
    key_footer,
    status,
)
from ..common.messages import MessageLatch
from ..common.service_status import ServiceState, classify, colour_for
from ..common.widgets import page_input
from ._support.state import configured, service, snapshot
from ._support.labels import alert_text, competition_label
from ._support.layout import (
    clock_label,
    kickoff_label,
    match_sort_key,
    matchday_label,
    minute_label,
    score_label,
)
from ._support.scoreboard import (
    MAX_MATCHES,
    SCORE_TOP,
    MatchCard,
    build_pages,
    draw_rows,
)
from services.sports.models import FeedSnapshot, MatchStatus

LIVE_PAGE = "150"
DETAIL_PAGE = "151"
ALERT_ROWS = 2


def _matches(feed_snapshot):
    return tuple(sorted(feed_snapshot.matches, key=match_sort_key))


def _card(match):
    return MatchCard(
        code=match.competition_code,
        kickoff=match.kickoff,
        home=match.home.short,
        away=match.away.short,
        score=score_label(match),
        status=_status_suffix(match).strip(),
        live=match.is_live,
        order=match.id,
        source=match,
    )


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
        cards = [
            _card(match)
            for match in matches
            if match.competition_code == code
        ]
        pages.extend(
            build_pages(
                code,
                cards,
                kickoff_label,
                sort_key=lambda card: (
                    card.source.home.name,
                    card.source.away.name,
                    card.source.id,
                ),
            )
        )
    return tuple(pages)


def _score_pager(ctx, pages):
    token = ctx.take_extension()
    offset = None
    if token:
        offset = next(
            (
                index
                for index, page in enumerate(pages)
                if page.code == token
            ),
            None,
        )
    pager = ctx.set_pager(
        len(pages),
        1,
        offset=offset,
        carousel=Carousel(hold=30.0, wrap=True),
    )
    if token and offset is None:
        MessageLatch(ctx).set(
            fit(f"NO LEAGUE {token}.", codec.COLS),
            pager.offset,
        )
    return pager


def _current_page(pager, pages):
    window = pager.window(pages)
    return window[0] if window else None


def _header(feed, feed_snapshot, page):
    if not configured(feed):
        return "SPORTS FEED NOT CONFIGURED"
    if feed_snapshot.error and not feed_snapshot.has_value:
        return "SCORES UNAVAILABLE."
    if not feed_snapshot.has_value:
        return "LOADING MATCHES..."
    if feed_snapshot.upcoming:
        return fit(
            f"NEXT MATCHDAY {matchday_label(feed_snapshot.match_date)}",
            codec.COLS,
        )
    if page is None:
        return "NO MATCHES TODAY."
    name = competition_label(page.code)
    if feed_snapshot.error:
        return fit(
            f"{name}  DATA STALE  UPD "
            f"{clock_label(feed_snapshot.updated_at)}",
            codec.COLS,
        )
    live = sum(1 for card in page.matches if card.live)
    return fit(
        f"{name}  LIVE {live}  UPD "
        f"{clock_label(feed_snapshot.updated_at)}",
        codec.COLS,
    )


def _state(feed, feed_snapshot):
    if not configured(feed):
        return ServiceState.MISSING
    return classify(feed_snapshot)


def _header_colour(feed, feed_snapshot):
    return colour_for(_state(feed, feed_snapshot))


def _empty_lines(feed, feed_snapshot):
    state = _state(feed, feed_snapshot)
    if state is ServiceState.MISSING:
        return ["SPORTS FEED NOT CONFIGURED", "SET FOOTBALL_API_KEY."]
    if state is ServiceState.UNAVAILABLE:
        return ["SCORES UNAVAILABLE.", "CHECK CONNECTION. RETRYING."]
    if state is ServiceState.LOADING:
        return ["LOADING MATCHES..."]
    return ["NO MATCHES TODAY.", "CHECK BACK ON MATCHDAY."]


def _hint(ctx, feed, feed_snapshot, window):
    error = MessageLatch(ctx).text()
    if error:
        return error
    state = _state(feed, feed_snapshot)
    if state is ServiceState.MISSING:
        return "SET FOOTBALL_API_KEY."
    if state is ServiceState.STALE and feed_snapshot.matches:
        return "DATA STALE. RETRYING."
    if state is ServiceState.UNAVAILABLE:
        return "SCORES UNAVAILABLE. RETRYING."
    if state is ServiceState.LOADING:
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
    MessageLatch(ctx).clear_if_moved(pager.offset)

    s = Screen()
    status_label = "150"
    if ctx.extension:
        status_label = (
            f"150#{page.code}"
            if page is not None
            else f"150#{ctx.extension}"
        )
    if pager.total:
        status_label += f" {pager.label}"
    status(s, status_label)
    prefix = "NEXT FIXTURES" if feed_snapshot.upcoming else "LIVE SCORES"
    title = f"{prefix} - {page.code}" if page is not None else prefix
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
        draw_rows(s, page)
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
            s.text(17 + index, 0, fit(alert_text(alert), codec.COLS))
    else:
        if feed_snapshot.upcoming:
            note = "NEXT MATCHDAY"
        else:
            live = any(match.is_live for match in feed_snapshot.matches)
            note = "WATCHING FOR GOALS" if live else "WAITING FOR KICKOFF"
        s.text(17, 0, note, fg=SECONDARY)

    waning = (
        not configured(feed)
        or feed_snapshot.error
        or MessageLatch(ctx).get()
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
    latch = MessageLatch(ctx)

    if value.isdigit() and 1 <= int(value) <= MAX_MATCHES:
        number = int(value)
        if number <= len(window):
            ctx.state["sports_match_id"] = window[number - 1].source.id
            latch.clear()
            return DETAIL_PAGE
        latch.set(f"NO MATCH {number}.", pager.offset)
        ctx.clear_input()
        return LIVE_PAGE

    if ctx.page_for(value) is not None:
        latch.clear()
        return None

    latch.set(
        fit(f"NO MATCH {sanitize(value)}.", codec.COLS),
        pager.offset,
    )
    ctx.clear_input()
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
    extensions=True,
)
def live_scores(ctx):
    return live_screen(ctx)
