"""Default row-0 header for the public pages."""

from minitel import Header, Screen

from .layout import status


class StatusHeader(Header):
    """Render a page's declared status, or preserve its body status row."""

    def render(self, ctx):
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
