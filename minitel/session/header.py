"""Session header selection, composition, and row-0 timing."""

from ..pagemodel.header import Header, HeaderContext, header_requires
from ..render.overlay import compose_row
from ..render.render import render_diff
from ..render.screen import Cell, Screen
from .action import Action


class HeaderMixin:
    def _header_for(self, page):
        if page is None:
            return None
        declared = getattr(page, "header", None)
        if declared is False:
            return None
        if declared is not None:
            if not isinstance(declared, Header):
                raise TypeError(
                    f"page {page.number!r} header must be None, False, "
                    "or a Header instance"
                )
            header_requires(declared)
            return declared
        app_header = getattr(self, "header", None)
        if app_header is False:
            return None
        if app_header is not None:
            if not isinstance(app_header, Header):
                raise TypeError(
                    "session header must be None, False, or a Header instance"
                )
            header_requires(app_header)
        return app_header

    def _header_interval_for(self, page):
        header = self._header_for(page)
        if header is None:
            return None
        interval = getattr(header, "tick_interval", None)
        if interval is None:
            return None
        if (
            isinstance(interval, bool)
            or not isinstance(interval, (int, float))
            or interval <= 0
        ):
            return None
        return float(interval)

    def _schedule_header(self):
        interval = self._header_interval_for(self.display_page)
        self._header_next = (
            self.clock() + interval if interval is not None else None
        )

    def _header_delay(self, now):
        if self._header_next is None:
            return None
        return max(0.0, self._header_next - now)

    def _header_due(self, now):
        return self._header_next is not None and now >= self._header_next

    @staticmethod
    def _copy_body_row(screen):
        return tuple(Cell(**vars(cell)) for cell in screen.rows[0])

    def _compose_header(self, screen, page):
        self._body_row = self._copy_body_row(screen)
        header = self._header_for(page)
        if header is None:
            self._header_next = None
            return screen
        ctx = HeaderContext(
            self,
            page,
            self.registry,
            header=header,
            body_row=self._body_row,
            status_text=self.status_text,
        )
        result = header.render(ctx)
        self._schedule_header()
        if result is None:
            return screen
        if not isinstance(result, Screen):
            raise TypeError(
                f"header on page {page.number!r} returned {type(result)!r}, "
                "expected Screen or None"
            )
        return compose_row(screen, 0, result.rows[0])

    def _refresh_header(self):
        if self.paused:
            return Action()
        base = self.screen
        if base is None:
            return Action()
        page = self.display_page
        header = self._header_for(page)
        if header is None:
            self._header_next = None
            return Action()
        ctx = HeaderContext(
            self,
            page,
            self.registry,
            header=header,
            body_row=self._body_row or self._copy_body_row(base),
            status_text=self.status_text,
        )
        result = header.render(ctx)
        self._schedule_header()
        if result is not None and not isinstance(result, Screen):
            raise TypeError(
                f"header on page {page.number!r} returned {type(result)!r}, "
                "expected Screen or None"
            )
        row = self._body_row if result is None else tuple(result.rows[0])
        if row is None:
            row = self._copy_body_row(base)
        composed = compose_row(base, 0, row)
        self.screen = composed
        return Action(
            raw=render_diff(base, composed, scroll=self.scroll_mode)
        )
