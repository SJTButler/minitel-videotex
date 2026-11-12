"""Page 199: a hidden developer directory of registered pages."""

from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from .common.layout import SECONDARY, footer, status
from .common.widgets import page_input

PAGE_SIZE = 12
NUMBER_LEGEND = "NUMBER: * SAVER  # EXT"
FLAG_LEGEND_1 = "FLAGS: D DYN  F FORM  T TRANS"
FLAG_LEGEND_2 = "       N NO-SLEEP  S SCROLL"


def _sort_key(page):
    number = page.number
    if number.isdigit():
        return (0, int(number))
    return (1, number)


def _entries(registry):
    return tuple(
        sorted(
            (
                page
                for page in registry.all()
                if not page.number.startswith("__")
            ),
            key=_sort_key,
        )
    )


def _flags(page):
    flags = []
    if page.tick_interval:
        flags.append("D")
    if page.form:
        flags.append("F")
    if page.transient:
        flags.append("T")
    if page.no_screensaver:
        flags.append("N")
    if page.scroll:
        flags.append("S")
    return "".join(flags)


def _number(page):
    suffix = "*" if page.screensaver else ""
    if page.extensions:
        suffix += "#"
    return f"{page.number}{suffix}"


def _title(page):
    name = page.screensaver
    if not isinstance(name, str) or not name:
        return page.title
    label = name.replace("_", " ").replace("-", " ").upper()
    if label == page.title.upper():
        return page.title
    return f"{label}: {page.title}"


def _line(page, aliases):
    alias_text = ",".join(alias for alias in aliases if alias)[:8]
    return (
        f"{_number(page):<5}{_title(page)[:20]:<21}"
        f"{alias_text:<8}{_flags(page)}"
    )[:codec.COLS]


def page_directory_screen(ctx):
    entries = _entries(ctx.registry)
    pager = ctx.set_pager(len(entries), PAGE_SIZE)
    visible = pager.window(entries)

    s = Screen()
    ctx.set_status("PAGE 199")
    status(s, "PAGE 199")
    s.text(1, 0, "PAGES", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(2, 0, f"REGISTERED PAGES {pager.label}", fg=SECONDARY)
    s.text(
        4,
        0,
        f"{'PAGE':<5}{'TITLE':<21}{'ALIAS':<8}FLAGS",
        fg=SECONDARY,
        underline=True,
    )
    for index, entry in enumerate(visible):
        s.text(
            5 + index,
            0,
            _line(entry, ctx.registry.aliases_for(entry)),
        )

    s.text(17, 0, NUMBER_LEGEND, fg=SECONDARY)
    s.text(18, 0, FLAG_LEGEND_1, fg=SECONDARY)
    s.text(19, 0, FLAG_LEGEND_2, fg=SECONDARY)
    page_input(s, ctx)
    footer(s)
    return s


@page("199", title="PAGES")
def page_directory(ctx):
    return page_directory_screen(ctx)
