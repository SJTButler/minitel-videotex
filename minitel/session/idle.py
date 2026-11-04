"""Session idle timing, screensaver takeover, and pager carousel."""

from ..pagemodel.model import PageContext
from ..protocol import codec
from ..render.screen import Screen
from .action import Action
from .screensaver import Screensaver


class IdleMixin:
    @property
    def idle_elapsed(self):
        return max(0.0, self.clock() - self.last_activity)

    @property
    def display_page(self):
        if self.screensaver_active and self.screensaver and self.screensaver.pages:
            return self._screensaver_current_page()
        return self.current

    def _screensaver_current_page(self):
        screensaver = self.screensaver
        carousel = screensaver.carousel
        pages = screensaver.pages
        if not carousel.active or len(pages) < 2:
            index = 0
        else:
            elapsed = max(0.0, self.clock() - self._screensaver_since)
            steps = int(elapsed // carousel.hold)
            if carousel.wrap:
                index = steps % len(pages)
            else:
                index = min(steps, len(pages) - 1)
        return screensaver.page(index)

    def set_screensaver(self, pages, *, after=120.0, hold=20.0, wrap=True):
        self.screensaver = Screensaver.from_spec(
            self.registry, pages, after=after, hold=hold, wrap=wrap
        )
        self.screensaver_active = False
        self._screensaver_since = 0.0
        self._screensaver_page = None
        self._screensaver_request = None
        return self.screensaver

    def disable_screensaver(self):
        self.screensaver = None
        self.screensaver_active = False
        self._screensaver_since = 0.0
        self._screensaver_page = None
        self._screensaver_request = None

    def request_screensaver(self, index=0):
        self._screensaver_request = index

    def _take_screensaver_request(self):
        if self._screensaver_request is None:
            return None
        index = self._screensaver_request
        self._screensaver_request = None
        return self.activate_screensaver(index)

    def activate_screensaver(self, index=0):
        if not self.screensaver or not self.screensaver.pages:
            return None
        pages = self.screensaver.pages
        now = self.clock()
        carousel = self.screensaver.carousel
        if carousel.active:
            self._screensaver_since = now - (index % len(pages)) * carousel.hold
        else:
            self._screensaver_since = now
        self.screensaver_active = True
        self._screensaver_page = self.display_page
        return self._render_screensaver()

    def _render_screensaver(self):
        page = self.display_page
        self.scroll_mode = bool(page.scroll)
        ctx = PageContext(self, page, self.registry)
        screen = page.render(ctx)
        if not isinstance(screen, Screen):
            raise TypeError(
                f"screensaver page {page.number!r} returned {type(screen)!r}, "
                "expected Screen"
            )
        screen.set_cursor(codec.ROWS - 1, 0, False)
        self._screensaver_page = page
        self.screen = screen
        self.screen_scroll_mode = self.scroll_mode
        return Action(screen=screen)

    def wake(self):
        if not self.screensaver_active:
            return Action()
        self.screensaver_active = False
        self._screensaver_page = None
        self._touch()
        return Action(screen=self.render())

    def _wake_from_input(self):
        self.parser = self._new_parser()
        return self.wake()

    def _screensaver_after(self):
        if not self.screensaver or not self.screensaver.pages:
            return None
        after = self.screensaver.after
        if after is None or after <= 0:
            return None
        return after

    def _idle_delay(self, now):
        after = self._screensaver_after()
        if after is None:
            return None
        if getattr(self.current, "no_screensaver", False):
            return None
        if self.current in self.screensaver.pages:
            return None
        return max(0.0, after - (now - self.last_activity))

    def _rotation_delay(self, now):
        if not self.screensaver_active:
            return None
        screensaver = self.screensaver
        if not screensaver or len(screensaver.pages) < 2:
            return None
        carousel = screensaver.carousel
        if not carousel.active:
            return None
        elapsed = now - self._screensaver_since
        steps = int(elapsed // carousel.hold)
        if not carousel.wrap and steps >= len(screensaver.pages) - 1:
            return None
        return (steps + 1) * carousel.hold - elapsed

    def _pager_carousel_delay(self, now):
        if self.screensaver_active or self.pager is None:
            return None
        carousel = self._pager_carousel
        if carousel is None or not carousel.active:
            return None
        if self._pager_carousel_next is None or self.pager.page_count < 2:
            return None
        if (
            not carousel.wrap
            and self.pager.page_index >= self.pager.page_count - 1
        ):
            return None
        if self._has_input_text():
            return None
        return max(0.0, self._pager_carousel_next - now)

    def _advance_pager_carousel(self, now):
        carousel = self._pager_carousel
        if carousel is None or self.pager is None:
            return Action()
        self.pager = self.pager.next(wrap=carousel.wrap)
        self.pagers[self.current.number] = self.pager
        self._pager_carousel_key = (
            self.pager.page_size,
            self.pager.offset,
            carousel,
        )
        self._pager_carousel_next = now + carousel.hold
        self._clear_active_field()
        return self.refresh()

    def next_timeout(self):
        if self.paused:
            return None
        now = self.clock()
        deadlines = []
        if self.screensaver_active:
            rotation = self._rotation_delay(now)
            if rotation is not None:
                deadlines.append(rotation)
            tick = self._page_tick_interval(
                self.display_page, pause_on_input=False
            )
            if tick is not None:
                deadlines.append(tick)
        else:
            idle = self._idle_delay(now)
            if idle is not None:
                deadlines.append(idle)
            pager_carousel = self._pager_carousel_delay(now)
            if pager_carousel is not None:
                deadlines.append(pager_carousel)
            tick = self.next_tick_delay()
            if tick is not None:
                deadlines.append(tick)
        return min(deadlines) if deadlines else None

    def on_timeout(self):
        if self.paused:
            return Action()
        now = self.clock()
        if self.screensaver_active:
            if self.display_page is not self._screensaver_page:
                return self._render_screensaver()
            return self.tick()
        idle = self._idle_delay(now)
        if idle is not None and idle <= 0:
            action = self.activate_screensaver()
            if action is not None:
                return action
        pager_carousel = self._pager_carousel_delay(now)
        if pager_carousel is not None and pager_carousel <= 0:
            return self._advance_pager_carousel(now)
        return self.tick()

    def _page_tick_interval(self, page, *, pause_on_input=True):
        if pause_on_input:
            field = self.active_field
            if field and field.cursor == "auto" and self.values.get(field.name, ""):
                return None
        interval = getattr(page, "tick_interval", None)
        if interval is None or interval <= 0:
            return None
        return interval

    def next_tick_delay(self):
        return self._page_tick_interval(self.current)
