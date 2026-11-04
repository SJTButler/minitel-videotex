"""Page 153: league tables."""

from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit, sanitize

from ..common.layout import SECONDARY, WARNING, key_footer, status
from ..common.messages import MessageLatch
from ..common.service_status import ServiceState, classify, updated_label
from ..common.widgets import page_input
from ._support.state import configured, service
from ._support.labels import competition_label
from .live import LIVE_PAGE
from ._support.layout import table_header, table_row

TABLES_PAGE = "153"
PAGE_SIZE = 10


def _competitions(feed):
    if feed is None:
        return ()
    return tuple(
        str(code).upper() for code in getattr(feed, "competitions", ())
    )


def _selected(ctx, feed):
    competitions = _competitions(feed)
    if not competitions:
        return ""
    if ctx.extension and ctx.extension in competitions:
        return ctx.extension
    code = str(ctx.state.get("sports_table_code") or competitions[0]).upper()
    return code if code in competitions else competitions[0]


def _state(feed, standings):
    if not configured(feed):
        return ServiceState.MISSING
    if standings is None:
        return ServiceState.LOADING
    return classify(standings)


def _header(feed, code, standings):
    state = _state(feed, standings)
    if state is ServiceState.MISSING:
        return "SPORTS FEED NOT CONFIGURED"
    name = competition_label(code)
    if state is ServiceState.LOADING:
        return f"{name}  LOADING TABLE..."
    if state is ServiceState.UNAVAILABLE:
        return f"{name}  TABLE UNAVAILABLE."
    if state is ServiceState.STALE:
        return f"{name}  OFFLINE {updated_label(standings)}".strip()
    return f"{name}  UPDATED {updated_label(standings)}".strip()


def _rows(feed, code, standings):
    if not configured(feed) or standings is None or not standings.has_value:
        return ()
    return tuple(standings.value or ())


def tables_screen(ctx):
    feed = service(ctx)
    competitions = _competitions(feed)
    extension_error = (
        f"NO LEAGUE {ctx.extension}."
        if ctx.extension and competitions and ctx.extension not in competitions
        else None
    )
    code = _selected(ctx, feed)
    if ctx.extension and ctx.extension in competitions:
        ctx.state["sports_table_code"] = ctx.extension
    standings = feed.standings(code) if configured(feed) else None
    rows = _rows(feed, code, standings)
    reset = ctx.state.pop("sports_table_reset", False)
    pager = ctx.set_pager(len(rows), PAGE_SIZE, offset=0 if reset else None)
    ctx.state["sports_table_offset"] = pager.offset
    MessageLatch(ctx).clear_if_moved(pager.offset)

    s = Screen()
    status_label = f"153#{ctx.extension}" if ctx.extension else "153"
    if pager.total:
        status_label += f" {pager.label}"
    status(s, status_label)
    s.text(1, 0, "TABLES", inverse=True, size=codec.DOUBLE_WIDTH)
    header = _header(feed, code, standings)
    warning = _state(feed, standings) is not ServiceState.READY
    s.text(
        2,
        0,
        fit(header, codec.COLS),
        fg=WARNING if warning else SECONDARY,
    )
    s.text(3, 0, table_header(), fg=SECONDARY, underline=True)

    window = pager.window(rows)
    for index, row in enumerate(window):
        s.text(4 + index, 0, table_row(row))

    if not window:
        if not configured(feed):
            lines = ["TABLE NOT CONFIGURED.", "SET FOOTBALL_API_KEY."]
        elif standings is not None and standings.error:
            lines = ["TABLE UNAVAILABLE.", "CHECK CONNECTION. RETRYING."]
        elif standings is None or not standings.has_value:
            lines = ["LOADING TABLE..."]
        else:
            lines = ["NO TABLE DATA."]
        for index, line in enumerate(lines):
            s.text(4 + index, 0, fit(line, codec.COLS), fg=WARNING)

    error = MessageLatch(ctx).text()
    if extension_error:
        hint = extension_error
    elif error:
        hint = error
    elif competitions:
        hint = (
            f"1-{len(competitions)} = LEAGUE, OR 153#{competitions[0]}"
        )
    else:
        hint = "NO LEAGUES CONFIGURED"
    s.text(
        15,
        0,
        fit(hint, codec.COLS),
        fg=WARNING if extension_error or error else SECONDARY,
    )
    s.text(16, 0, "SUITE = NEXT PAGE", fg=SECONDARY)
    page_input(s, ctx, cursor="auto")
    key_footer(s, ("SUITE=NEXT", "RETOUR=BACK", "SOMMAIRE=HOME"))
    s.text(23, 0, "150=LIVE  154=STATUS", fg=SECONDARY)
    return s


def submit_tables(ctx, line):
    value = line.strip()
    feed = service(ctx)
    competitions = _competitions(feed)
    offset = ctx.state.get("sports_table_offset", 0)
    latch = MessageLatch(ctx)
    if value.isdigit() and competitions:
        number = int(value)
        if 1 <= number <= len(competitions):
            code = competitions[number - 1]
            ctx.state["sports_table_code"] = code
            ctx.state["sports_table_reset"] = True
            latch.clear()
            ctx.clear_input()
            return f"{TABLES_PAGE}#{code}"
        latch.set(
            fit(f"NO LEAGUE {number}.", codec.COLS),
            offset,
        )
        ctx.clear_input()
        return ctx.page.number

    if ctx.page_for(value) is not None:
        latch.clear()
        return None

    latch.set(
        fit(f"NO LEAGUE {sanitize(value)}.", codec.COLS),
        offset,
    )
    ctx.clear_input()
    return ctx.page.number


@page(
    TABLES_PAGE,
    title="TABLES",
    requires=("sports",),
    back_page=LIVE_PAGE,
    tick_interval=5.0,
    on_submit=submit_tables,
    on_tick=tables_screen,
    extensions=True,
)
def tables(ctx):
    return tables_screen(ctx)
