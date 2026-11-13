"""Default row-0 headers for the public pages."""

from minitel import Header, Screen
from minitel.protocol import codec
from minitel.text import fit, sanitize

from .layout import status


def announcement_row(text):
    screen = Screen()
    screen.fill(0, 0, codec.COLS, " ", inverse=True)
    screen.text(
        0, 0, fit(sanitize(text), codec.COLS), inverse=True
    )
    return screen


class StatusHeader(Header):
    """Render the current announcement, then the page status."""

    def render(self, ctx):
        if ctx.announcement is not None:
            return announcement_row(ctx.announcement.text)
        if ctx.screensaver_active:
            return None
        if ctx.status_text is not None:
            screen = Screen()
            status(screen, ctx.status_text)
            return screen
        if any(
            cell.ch != " " or cell.inverse or cell.underline
            for cell in ctx.body_row
        ):
            return None
        screen = Screen()
        status(screen, f"PAGE {ctx.body_page.number}")
        return screen


class AnnouncementHeader(Header):
    """Show announcements only; leave the body's own row 0 otherwise."""

    def render(self, ctx):
        if ctx.announcement is None:
            return None
        return announcement_row(ctx.announcement.text)
