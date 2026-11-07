"""Page 155: full-screen football alert feed."""

from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit

from ..common.layout import SECONDARY, WARNING, status
from ._support.layout import local_time
from ._support.labels import alert_text
from ._support.state import configured, service, snapshot
from services.sports.models import FeedSnapshot

VIDIPRINTER_PAGE = "155"


def _alert_line(alert):
    stamp = local_time(alert.at)
    prefix = stamp.strftime("%H:%M") if stamp else "--:--"
    return f"{prefix} {alert_text(alert)}"


def _lines(feed, feed_snapshot):
    if not configured(feed):
        return ("SPORTS FEED NOT CONFIGURED.", "SET FOOTBALL_API_KEY IN .ENV.")

    alerts = feed_snapshot.alerts
    if alerts:
        return tuple(_alert_line(alert) for alert in reversed(alerts))

    if feed_snapshot.error:
        return ("DATA UNAVAILABLE.", "RETRYING...")
    if feed_snapshot.loading:
        return ("LOADING ALERTS...",)
    if feed_snapshot.upcoming:
        return ("NEXT MATCHDAY",)
    if any(match.is_live for match in feed_snapshot.matches):
        return ("WATCHING FOR GOALS",)
    return ("WAITING FOR KICKOFF",)


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
    status(screen, f"PAGE 155 {view.line_number}/{view.total}")
    colour = WARNING if not configured(feed) else SECONDARY
    for row, line in enumerate(view.window(lines), start=1):
        screen.text(row, 0, fit(line, codec.COLS - 1), fg=colour)
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
