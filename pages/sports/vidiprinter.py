"""Page 155: full-screen football alert feed."""

from dataclasses import dataclass

from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from ..common.layout import SECONDARY, WARNING, status
from ._support.layout import local_time
from ._support.labels import alert_text
from ._support.state import configured, service, snapshot
from services.sports.models import FeedSnapshot

VIDIPRINTER_PAGE = "155"
BRIGHT = codec.WHITE
DIM = SECONDARY


@dataclass(frozen=True)
class AlertLine:
    text: str
    segments: tuple[tuple[str, int | None], ...]


def _fit_segments(segments, width=codec.COLS - 1):
    fitted = []
    parts = []
    used = 0
    for value, colour in segments:
        if used >= width:
            break
        piece = value[:width - used]
        if not piece:
            continue
        fitted.append((piece, colour))
        parts.append(piece)
        used += len(piece)
    return AlertLine("".join(parts), tuple(fitted))


def _status_line(text, colour):
    return AlertLine(text, ((text, colour),))


def _alert_line(alert):
    stamp = local_time(alert.at)
    prefix = f"{stamp:%H:%M} " if stamp else "--:-- "
    competition = (
        f"{alert.competition[:4]:<4} " if alert.competition else ""
    )
    event = alert_text(alert)
    text = f"{prefix}{competition}{event}"
    start = len(prefix) + len(competition)
    home_pos = text.find(alert.home, start)
    away_pos = text.find(
        alert.away,
        home_pos + len(alert.home) if home_pos >= 0 else start,
    )
    if home_pos < 0 or away_pos < 0:
        return _fit_segments(((text, None),))

    home_colour = (
        BRIGHT if alert.side == "home" else DIM if alert.side == "away" else None
    )
    away_colour = (
        BRIGHT if alert.side == "away" else DIM if alert.side == "home" else None
    )
    return _fit_segments(
        (
            (text[:home_pos], None),
            (alert.home, home_colour),
            (text[home_pos + len(alert.home):away_pos], None),
            (alert.away, away_colour),
            (text[away_pos + len(alert.away):], None),
        )
    )


def _lines(feed, feed_snapshot):
    if not configured(feed):
        return (
            _status_line("SPORTS FEED NOT CONFIGURED.", WARNING),
            _status_line("SET FOOTBALL_API_KEY IN .ENV.", WARNING),
        )

    alerts = feed_snapshot.alerts
    if alerts:
        return tuple(_alert_line(alert) for alert in reversed(alerts))

    if feed_snapshot.error:
        return (
            _status_line("DATA UNAVAILABLE.", WARNING),
            _status_line("RETRYING...", WARNING),
        )
    if feed_snapshot.loading:
        return (_status_line("LOADING ALERTS...", SECONDARY),)
    if feed_snapshot.upcoming:
        return (_status_line("NEXT MATCHDAY", SECONDARY),)
    if any(match.is_live for match in feed_snapshot.matches):
        return (_status_line("WATCHING FOR GOALS", SECONDARY),)
    return (_status_line("WAITING FOR KICKOFF", SECONDARY),)


def vidiprinter_screen(ctx):
    feed = service(ctx)
    feed_snapshot = snapshot(ctx) if feed is not None else FeedSnapshot(
        error="NOT CONFIGURED"
    )
    lines = _lines(feed, feed_snapshot)
    default_follow = True if ctx.viewport is None else None
    view = ctx.set_viewport(
        len(lines), codec.ROWS - 1, follow=default_follow
    )

    screen = Screen()
    screen.paint_order = "up"
    if feed_snapshot.alerts and not ctx.state.get("vidiprinter_loaded"):
        ctx.state["vidiprinter_loaded"] = True
        screen.force_full = True
    status(screen, f"PAGE 155 {view.line_number}/{view.total}")
    for row, line in enumerate(view.window(lines), start=1):
        col = 0
        for text, colour in line.segments:
            if colour is None:
                screen.text(row, col, text)
            else:
                screen.text(row, col, text, fg=colour)
            col += len(text)
    return screen


@page(
    VIDIPRINTER_PAGE,
    title="VIDIPRINTER",
    aliases=("6",),
    requires=("sports",),
    back_page="150",
    tick_interval=5.0,
    on_tick=vidiprinter_screen,
    scroll=True,
    no_screensaver=True,
)
def vidiprinter(ctx):
    return vidiprinter_screen(ctx)
