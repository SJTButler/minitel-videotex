"""Page 153: league tables."""

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen
from minitel.text import fit, sanitize

from ..layout import SECONDARY, WARNING, key_footer, page_input, status, updated_label
from .common import clear_error, configured, service, set_error
from .live import LIVE_PAGE
from .layout import table_header, table_row

TABLES_PAGE = "153"
PAGE_SIZE = 10


def _competitions(feed):
    return tuple(getattr(feed, "competitions", ())) if feed is not None else ()


def _selected(ctx, feed):
    competitions = _competitions(feed)
    if not competitions:
        return ""
    code = str(ctx.state.get("sports_table_code") or competitions[0]).upper()
    return code if code in competitions else competitions[0]


def _header(feed, code, standings):
    if not configured(feed):
        return "SPORTS FEED NOT CONFIGURED"
    name = feed.competition_name(code)
    if standings is None:
        return f"{name}  LOADING TABLE..."
    if standings.error and not standings.has_value:
        return f"{name}  TABLE UNAVAILABLE."
    if standings.error:
        return f"{name}  OFFLINE {updated_label(standings)}".strip()
    return f"{name}  UPDATED {updated_label(standings)}".strip()


def _rows(feed, code, standings):
    if not configured(feed) or standings is None or not standings.has_value:
        return ()
    return tuple(standings.value or ())


def tables_screen(ctx):
    feed = service(ctx)
    code = _selected(ctx, feed)
    standings = feed.standings(code) if configured(feed) else None
    rows = _rows(feed, code, standings)
    reset = ctx.state.pop("sports_table_reset", False)
    pager = ctx.set_pager(len(rows), PAGE_SIZE, offset=0 if reset else None)

    s = Screen()
    status(s, f"153 {pager.label}" if pager.total else "153")
    s.text(1, 0, "TABLES", inverse=True, size=codec.DOUBLE_WIDTH)
    header = _header(feed, code, standings)
    warning = (
        not configured(feed)
        or standings is None
        or bool(standings.error)
    )
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

    competitions = _competitions(feed)
    error = ctx.state.get("sports_error")
    if error:
        hint = error
    elif competitions:
        hint = f"1-{len(competitions)} = LEAGUE"
    else:
        hint = "NO LEAGUES CONFIGURED"
    s.text(
        15,
        0,
        fit(hint, codec.COLS),
        fg=WARNING if error else SECONDARY,
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
    if value.isdigit() and competitions:
        number = int(value)
        if 1 <= number <= len(competitions):
            ctx.state["sports_table_code"] = competitions[number - 1]
            ctx.state["sports_table_reset"] = True
            clear_error(ctx)
            ctx.values["input"] = ""
            return TABLES_PAGE
        set_error(
            ctx,
            fit(f"NO LEAGUE {number}.", codec.COLS),
            0,
        )
        ctx.values["input"] = ""
        return TABLES_PAGE

    if ctx.page_for(value) is not None:
        clear_error(ctx)
        return None

    set_error(
        ctx,
        fit(f"NO LEAGUE {sanitize(value)}.", codec.COLS),
        0,
    )
    ctx.values["input"] = ""
    return TABLES_PAGE


@page(
    TABLES_PAGE,
    title="TABLES",
    requires=("sports",),
    back_page=LIVE_PAGE,
    tick_interval=5.0,
    on_submit=submit_tables,
    on_tick=tables_screen,
)
def tables(ctx):
    return tables_screen(ctx)
