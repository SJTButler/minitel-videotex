"""Page 110: the news service directory."""

from dataclasses import dataclass

from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen

from ..common.layout import (
    ACCENT,
    FIELD_ROW,
    SECONDARY,
    key_footer,
    status,
)
from ..common.service_status import describe
from ..common.widgets import page_input


@dataclass(frozen=True)
class NewsServiceEntry:
    number: str
    label: str
    page: str
    service: str


NEWS_SERVICES = (
    NewsServiceEntry("1", "HACKER NEWS", "111", "hackernews"),
)


def directory_screen(ctx):
    s = Screen()
    status(s, "PAGE 110")
    s.text(1, 0, "NEWS", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(2, 0, "CHOOSE A NEWS SERVICE", fg=SECONDARY)

    for index, entry in enumerate(NEWS_SERVICES):
        row = 4 + index * 3
        if row >= FIELD_ROW - 1:
            break
        s.text(row, 0, f"{entry.number} ", fg=ACCENT, inverse=True)
        s.text(row, 3, entry.label[:codec.COLS - 3])
        service = ctx.service(entry.service)
        snapshot = service.front_page() if service is not None else None
        page_status = describe(
            snapshot,
            empty=bool(snapshot and snapshot.has_value and not snapshot.value),
            missing_text="NOT CONFIGURED",
            loading_text="LOADING",
            unavailable_text="UNAVAILABLE",
            empty_text="NO HEADLINES",
            stale_prefix="OFFLINE - CACHED",
            stale_time=False,
        )
        s.text(
            row + 1, 2, page_status.text[:codec.COLS - 2],
            fg=page_status.colour, underline=True,
        )

    page_input(s, ctx, cursor="auto")
    key_footer(s, ("RETOUR=BACK", "SOMMAIRE=HOME"))
    s.text(23, 0, "TYPE 1, THEN ENVOI", fg=SECONDARY)
    return s


def submit_directory(ctx, line):
    value = line.strip()
    for entry in NEWS_SERVICES:
        if value == entry.number:
            return entry.page
    return None


@page(
    "110",
    title="NEWS",
    aliases=("1",),
    requires=("hackernews",),
    tick_interval=5.0,
    on_submit=submit_directory,
    on_tick=directory_screen,
)
def news(ctx):
    return directory_screen(ctx)
