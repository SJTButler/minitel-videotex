"""Default row-0 headers for the public pages."""

from minitel import Header, Screen
from minitel.protocol import codec
from minitel.text import fit, sanitize

from .layout import STATUS_MARGIN, status

CHYRON_WIDTH = codec.COLS - STATUS_MARGIN


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


class ChyronHeader(StatusHeader):
    """Opt-in right-to-left announcement ticker."""

    tick_interval = 1.0
    step_columns = 2

    def announcement_duration(self, announcement):
        text = sanitize(announcement.text)
        speed = self.step_columns / self.tick_interval
        travel = (len(text) + CHYRON_WIDTH - 1) / speed
        return max(12.0, travel)

    def render(self, ctx):
        if ctx.announcement is None:
            return super().render(ctx)
        text = sanitize(ctx.announcement.text)
        source = " " * (CHYRON_WIDTH - 1) + text + " " * CHYRON_WIDTH
        position = int(
            max(0.0, ctx.announcement_elapsed) / self.tick_interval
        ) * self.step_columns
        start = min(position, max(0, len(source) - CHYRON_WIDTH))
        window = source[start:start + CHYRON_WIDTH]
        if len(window) < CHYRON_WIDTH:
            window += " " * (CHYRON_WIDTH - len(window))
        screen = Screen()
        screen.fill(0, 0, codec.COLS, " ", inverse=True)
        screen.text(0, 0, window, inverse=True)
        screen.paint = "cell"
        return screen
