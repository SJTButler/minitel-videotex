"""Page 154: feed status and quota."""

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen
from minitel.text import age, fit, sanitize, wrap

from ..layout import SECONDARY, WARNING, key_footer, page_input, status
from .common import configured, service
from .layout import clock_label
from .live import LIVE_PAGE
from services.sports.models import FeedSnapshot

STATUS_PAGE = "154"


def _line(s, row, label, value, *, colour=SECONDARY):
    text = fit(f"{label}{value}", codec.COLS)
    s.text(row, 0, text, fg=colour)
    return text


def status_screen(ctx):
    feed = service(ctx)
    feed_snapshot = feed.snapshot() if feed is not None else FeedSnapshot(
        error="NOT CONFIGURED"
    )
    config = getattr(feed, "config", None)

    s = Screen()
    status(s, "PAGE 154")
    s.text(1, 0, "FEED STATUS", inverse=True, size=codec.DOUBLE_WIDTH)

    if not configured(feed):
        _line(s, 3, "PROVIDER: ", "NOT CONFIGURED", colour=WARNING)
        _line(s, 4, "SET ", "FOOTBALL_API_KEY IN .ENV", colour=SECONDARY)
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
        s.text(23, 0, "DATA: FOOTBALL-DATA.ORG", fg=SECONDARY)
        return s

    base = config.base_url.replace("https://", "").replace("http://", "")
    _line(s, 3, "PROVIDER: ", "FOOTBALL-DATA.ORG")
    _line(s, 4, "API: ", base.upper())
    _line(
        s,
        5,
        "KEY: ",
        "SET" if config.token else "MISSING",
        colour=SECONDARY if config.token else WARNING,
    )
    _line(s, 6, "LEAGUES: ", " ".join(feed.competitions))

    last_ok = clock_label(feed_snapshot.updated_at) if feed_snapshot.has_value else "NEVER"
    age_text = age(feed_snapshot.age()) if feed_snapshot.has_value else "--"
    _line(s, 7, "LAST OK: ", f"{last_ok}  AGE: {age_text}")
    quota = (
        "--" if feed_snapshot.quota_remaining is None
        else str(feed_snapshot.quota_remaining)
    )
    reset = (
        "--" if feed_snapshot.quota_reset is None
        else f"{feed_snapshot.quota_reset}S"
    )
    _line(s, 8, "QUOTA: ", f"{quota} LEFT  RESET {reset}")
    _line(s, 9, "LIVE: ", "PLAN DEPENDENT", colour=WARNING)

    if feed_snapshot.error:
        _line(s, 10, "LAST ERROR", "", colour=WARNING)
        for index, text in enumerate(
            wrap(sanitize(feed_snapshot.error), codec.COLS, max_lines=2)
        ):
            s.text(11 + index, 0, text, fg=WARNING)
    else:
        _line(s, 10, "LAST ERROR: ", "NONE")

    if config is not None:
        _line(
            s,
            13,
            "POLL: ",
            f"{config.live_interval:.0f}S LIVE  "
            f"{config.day_interval:.0f}S DAY  "
            f"{config.idle_interval:.0f}S IDLE",
        )

    s.text(15, 0, "DATA: FOOTBALL-DATA.ORG", fg=SECONDARY)
    s.text(16, 0, "FREE PLAN SCORES MAY BE DELAYED", fg=SECONDARY)
    page_input(s, ctx, cursor="auto")
    key_footer(s, ("RETOUR=SCORES", "SOMMAIRE=HOME"))
    s.text(23, 0, "150=LIVE  153=TABLES", fg=SECONDARY)
    return s


@page(
    STATUS_PAGE,
    title="FEED STATUS",
    requires=("sports",),
    back_page=LIVE_PAGE,
    tick_interval=5.0,
    on_tick=status_screen,
    no_screensaver=True,
)
def feed_status(ctx):
    return status_screen(ctx)
