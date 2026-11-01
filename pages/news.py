"""Page 110: the news service directory."""

from dataclasses import dataclass

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from .layout import (
    ACCENT,
    SECONDARY,
    WARNING,
    FIELD_ROW,
    key_footer,
    page_input,
    status,
    updated_label,
)


@dataclass(frozen=True)
class NewsServiceEntry:
    number: str
    label: str
    page: str
    service: str


NEWS_SERVICES = (
    NewsServiceEntry("1", "HACKER NEWS", "111", "hackernews"),
)


def status_colour(text):
    if text.startswith(("NOT CONFIGURED", "UNAVAILABLE", "OFFLINE")):
        return WARNING
    return SECONDARY


def service_status(service):
    if service is None:
        return "NOT CONFIGURED"
    snapshot = service.front_page()
    if snapshot.loading and not snapshot.has_value:
        return "LOADING"
    if snapshot.error and not snapshot.has_value:
        return "UNAVAILABLE"
    if snapshot.error and snapshot.has_value:
        return "OFFLINE - CACHED"
    if snapshot.has_value:
        if not snapshot.value:
            return "NO HEADLINES"
        return "UPDATED " + updated_label(snapshot)
    return "LOADING"


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
        status_text = service_status(ctx.services.get(entry.service))
        s.text(
            row + 1, 2, status_text[:codec.COLS - 2],
            fg=status_colour(status_text), underline=True,
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
    tick_interval=5.0,
    on_submit=submit_directory,
    on_tick=directory_screen,
)
def news(ctx):
    return directory_screen(ctx)
