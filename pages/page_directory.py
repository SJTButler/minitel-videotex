"""Page 199: a hidden developer directory of registered pages."""

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from .common.layout import SECONDARY, footer, status
from .common.widgets import page_input

PAGE_SIZE = 15
FLAG_LEGEND = "* SAVER D DYN F FORM T TRANS N NO-SLEEP"


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
    return " ".join(flags)


def _number(page):
    suffix = "*" if page.screensaver else ""
    return f"{page.number}{suffix}"


def _title(page):
    name = page.screensaver
    if not isinstance(name, str) or not name:
        return page.title
    label = name.replace("_", " ").replace("-", " ").upper()
    if label == page.title.upper():
        return page.title
    return f"{label}: {page.title}"


def _line(page):
    aliases = ",".join(alias for alias in page.aliases if alias)[:8]
    return (
        f"{_number(page):<5}{_title(page)[:20]:<21}{aliases:<8}{_flags(page)}"
    )[:codec.COLS]


def page_directory_screen(ctx):
    entries = _entries(ctx.registry)
    pager = ctx.set_pager(len(entries), PAGE_SIZE)
    visible = pager.window(entries)

    s = Screen()
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
        s.text(5 + index, 0, _line(entry))

    s.text(23, 0, FLAG_LEGEND, fg=SECONDARY)
    page_input(s, ctx)
    footer(s)
    return s


@page("199", title="PAGES")
def page_directory(ctx):
    return page_directory_screen(ctx)
