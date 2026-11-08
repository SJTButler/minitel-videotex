"""Transport-neutral session orchestration."""

import time

from ..design.stops import reveal_viewport
from ..pagemodel.model import PageContext
from ..protocol import codec
from ..render.render import render_diff, reset
from ..render.screen import Screen
from ..terminal.power import Power, PowerSignals, PowerWatcher
from .action import Action
from .editing import EditingMixin
from .idle import IdleMixin
from .navigation import NavigationMixin
from .power import PowerMixin
from .screensaver import Screensaver


class Session(NavigationMixin, EditingMixin, IdleMixin, PowerMixin):
    def __init__(self, registry, profile, *, initial="100", fallback=None,
                 guide=None, echo=False, services=None, screensaver=None,
                 power=None, clock=time.monotonic):
        self.registry = registry
        self.profile = profile
        self.initial = initial
        self.fallback = fallback or registry.get(initial)
        self.guide = guide
        self.echo = echo
        self.services = dict(services or {})
        self.power_signals = (
            power if isinstance(power, PowerSignals) else PowerSignals()
        )
        self.power = PowerWatcher(self.power_signals)
        self.parser = codec.InputParser()
        self.paused = False
        self.last_key = ""
        self.state = {}
        self.history = []
        self.current = registry.resolve(initial)
        self._extension_pending = False
        self.fields = []
        self.values = {}
        self.active = 0
        self.active_name = None
        self.requested_focus = None
        self.pager = None
        self.pagers = {}
        self.viewport = None
        self.viewports = {}
        self.stops = None
        self.choice = None
        self._resources = []
        self._closed = False
        self._pager_carousel = None
        self._pager_carousel_next = None
        self._pager_carousel_key = None
        self.screen = None
        self.scroll_mode = False
        self.screen_scroll_mode = False
        self.clock = clock
        self.screensaver = (
            screensaver
            if isinstance(screensaver, Screensaver)
            else Screensaver.from_spec(registry, screensaver)
            if screensaver is not None
            else None
        )
        self.screensaver_active = False
        self.last_activity = self.clock()
        self._screensaver_since = 0.0
        self._screensaver_page = None
        self._screensaver_request = None

    def echo_override(self):
        """Assert the terminal's local echo mode for this session."""
        return codec.echo_mode(not self.echo)

    def _touch(self):
        now = self.clock()
        self.last_activity = now
        if self._pager_carousel is not None and self._pager_carousel.active:
            self._pager_carousel_next = now + self._pager_carousel.hold

    def _new_parser(self):
        return codec.InputParser()

    def _new_power(self):
        return PowerWatcher(self.power_signals)

    def _reset_page(self):
        self.fields = []
        self.values = {}
        self.active = 0
        self.active_name = None
        self.requested_focus = None
        self.pager = None
        self.viewport = None
        self.stops = None
        self.choice = None
        self._pager_carousel = None
        self._pager_carousel_next = None
        self._pager_carousel_key = None

    def add_resource(self, resource):
        if self._closed:
            raise RuntimeError("session is closed")
        if resource is None:
            raise TypeError("resource must not be None")
        if not any(existing is resource for existing in self._resources):
            self._resources.append(resource)
        return resource

    def close(self):
        if self._closed:
            return
        self._closed = True
        errors = []
        for resource in reversed(self._resources):
            hook = getattr(resource, "close", None)
            if hook is None:
                continue
            try:
                hook()
            except Exception as exc:
                errors.append(exc)
        self._resources.clear()
        if errors:
            raise errors[0]

    def _adopt_pager(self, pager, carousel):
        if pager is None:
            self.pager = None
            self.pagers.pop(self.current.number, None)
            self._pager_carousel = None
            self._pager_carousel_next = None
            self._pager_carousel_key = None
            return
        self.pager = pager
        self.pagers[self.current.number] = pager
        key = (pager.page_size, pager.offset, carousel)
        if (
            key != self._pager_carousel_key
            or pager.page_count < 2
            or (
                self._pager_carousel_next is None
                and carousel is not None
                and carousel.active
            )
        ):
            self._pager_carousel_key = key
            self._pager_carousel = carousel
            if (
                carousel is not None
                and carousel.active
                and pager.page_count >= 2
            ):
                self._pager_carousel_next = self.clock() + carousel.hold
            else:
                self._pager_carousel_next = None
        else:
            self._pager_carousel = carousel

    def _adopt_viewport(self, viewport):
        if viewport is None:
            self.viewport = None
            self.viewports.pop(self.current.number, None)
            return
        self.viewport = viewport
        self.viewports[self.current.number] = viewport

    def _reveal_stop(self):
        if self.stops is None or self.viewport is None:
            return
        stop = self.stops.selected_stop
        if stop is None:
            return
        viewport = reveal_viewport(self.viewport, stop.line)
        if viewport is not None:
            self.viewport = viewport
            self.viewports[self.current.number] = viewport

    def start(self):
        self.paused = False
        self.parser = self._new_parser()
        self.power = self._new_power()
        self.screensaver_active = False
        self._extension_pending = False
        self._touch()
        return self.render()

    def refresh(self):
        if self.paused:
            return Action()
        old = self.screen
        old_scroll = self.screen_scroll_mode
        new = self.render()
        if (
            old is None
            or old_scroll != self.screen_scroll_mode
            or getattr(new, "force_full", False)
        ):
            return Action(screen=new)
        return Action(raw=render_diff(old, new, scroll=self.scroll_mode))

    def render(self):
        self.scroll_mode = bool(self.current.scroll)
        ctx = PageContext(self, self.current, self.registry)
        screen = self.current.render(ctx)
        self._extension_pending = False
        if not isinstance(screen, Screen):
            raise TypeError(
                f"page {self.current.number!r} returned {type(screen)!r}, expected Screen"
            )
        if ctx._viewport_set and ctx.pager is not None:
            raise ValueError(
                f"page {self.current.number!r} cannot declare both a viewport "
                "and a pager"
            )
        if ctx._choice_set and (ctx._viewport_set or ctx.pager is not None):
            raise ValueError(
                f"page {self.current.number!r} cannot mix a choice with "
                "a viewport or pager"
            )
        if self.current.form and ctx.fields and ctx.pager is not None:
            raise ValueError(
                f"page {self.current.number!r} cannot declare both form fields "
                "and a pager"
            )
        if self.current.form and ctx.fields and ctx._viewport_set:
            raise ValueError(
                f"page {self.current.number!r} cannot declare both form fields "
                "and a viewport"
            )
        self._adopt_pager(ctx.pager, ctx.pager_carousel)
        self._adopt_viewport(ctx.viewport if ctx._viewport_set else None)
        self.stops = ctx.stops if ctx._stops_set else None
        self.choice = ctx.choice if ctx._choice_set else None
        self.fields = ctx.fields
        names = [field.name for field in self.fields]
        self.values = {name: self.values.get(name, "") for name in names}

        focus = self.requested_focus
        self.requested_focus = None
        if focus and focus in names:
            self.active = names.index(focus)
            self.active_name = focus
        elif self.active_name and self.active_name in names:
            self.active = names.index(self.active_name)
        else:
            self.active = 0
            self.active_name = names[0] if names else None

        field = self.active_field
        if field is not None and field.visible:
            value = self.values.get(field.name, "")
            col = field.col + min(len(value), field.width)
            screen.set_cursor(field.row, col, self._cursor_visible())
        else:
            screen.set_cursor(codec.ROWS - 1, 0, False)
        self.screen = screen
        self.screen_scroll_mode = self.scroll_mode
        return screen

    def tick(self):
        if self.paused:
            return Action()
        page = self.display_page
        self.scroll_mode = bool(page.scroll)
        if self.screensaver_active:
            if self._page_tick_interval(page, pause_on_input=False) is None:
                return Action()
        elif self.next_tick_delay() is None:
            return Action()
        ctx = PageContext(self, page, self.registry)
        frame = page.on_tick(ctx)
        if not self.screensaver_active and ctx.pager is not None:
            self._adopt_pager(ctx.pager, ctx.pager_carousel)
        if not self.screensaver_active and ctx._viewport_set:
            self._adopt_viewport(ctx.viewport)
        if not self.screensaver_active and ctx._stops_set:
            self.stops = ctx.stops
        if not self.screensaver_active and ctx._choice_set:
            self.choice = ctx.choice
        if frame is None:
            return Action()
        if isinstance(frame, (bytes, bytearray)):
            frame = bytes(frame)
            if frame:
                frame = reset() + frame
            if not self.screensaver_active and frame and self.active_field is not None:
                frame += self._focus_frame()
            return Action(raw=frame)
        if isinstance(frame, Screen):
            if self.screensaver_active:
                frame.set_cursor(codec.ROWS - 1, 0, False)
            else:
                field = self.active_field
                if field is not None and field.visible:
                    value = self.values.get(field.name, "")
                    col = field.col + min(len(value), field.width)
                    frame.set_cursor(field.row, col, self._cursor_visible())
                else:
                    frame.set_cursor(codec.ROWS - 1, 0, False)
            old = self.screen
            if (
                old is None
                or self.scroll_mode != self.screen_scroll_mode
                or getattr(frame, "force_full", False)
            ):
                self.screen = frame
                self.screen_scroll_mode = self.scroll_mode
                return Action(screen=frame)
            diff = render_diff(old, frame, scroll=self.scroll_mode)
            self.screen = frame
            self.screen_scroll_mode = self.scroll_mode
            return Action(raw=diff)
        raise TypeError(
            f"page {page.number!r} tick returned {type(frame)!r}; "
            "expected bytes, Screen, or None"
        )

    def handle(self, event):
        if self.screensaver_active:
            if self._is_user_input(event):
                return self._wake_from_input()
            return Action()
        self._touch()
        if isinstance(event, codec.Text):
            return self.text_event(event)
        if isinstance(event, codec.Enter):
            return self.submit()
        if isinstance(event, codec.Function):
            return self.function(event.name)
        if isinstance(event, codec.Key):
            if self.viewport is not None and event.name in ("up", "down"):
                if event.name == "up":
                    self.viewport = self.viewport.line_up()
                else:
                    self.viewport = self.viewport.line_down()
                self.viewports[self.current.number] = self.viewport
                return self.refresh()
            ctx = PageContext(self, self.current, self.registry)
            result = self.current.on_key(ctx, event.name)
            requested = self._take_screensaver_request()
            if requested is not None:
                return requested
            page = self.resolve_page(result)
            if page is not None:
                return self.navigate(page)
            return Action()
        return Action()

    def function(self, name):
        if name == "ENVOI":
            return self.submit()

        if name == "CORRECTION":
            return self.correction()

        if name == "ANNULATION":
            return self.annulation()

        if name == "SOMMAIRE":
            return self.home()

        if self.current.form and self.fields:
            if name == "SUITE":
                if self.active < len(self.fields) - 1:
                    self.active += 1
                    self.active_name = self.fields[self.active].name
                    return self.refresh()
                return Action()
            if name == "RETOUR":
                if self.active > 0:
                    self.active -= 1
                    self.active_name = self.fields[self.active].name
                    return self.refresh()
                return self._back_or_parent()

        if (
            self.choice is not None
            and self.choice.total
            and name in ("SUITE", "RETOUR")
        ):
            if name == "SUITE":
                updated = self.choice.next()
                if updated != self.choice:
                    self.choice = updated
                    self._clear_active_field()
                    return self.refresh()
                return Action()
            if self.choice.selected not in (None, 0):
                self.choice = self.choice.prev()
                self._clear_active_field()
                return self.refresh()

        if self.viewport is not None:
            if (
                self.stops is not None
                and len(self.stops.stops) > 1
                and name in ("SUITE", "RETOUR")
            ):
                self.stops = (
                    self.stops.next() if name == "SUITE"
                    else self.stops.prev()
                )
                self._reveal_stop()
                self._clear_active_field()
                return self.refresh()
            if name == "SUITE":
                self.viewport = self.viewport.step_down()
                self.viewports[self.current.number] = self.viewport
                self._clear_active_field()
                return self.refresh()
            if name == "RETOUR":
                if not self.viewport.at_top:
                    self.viewport = self.viewport.step_up()
                    self.viewports[self.current.number] = self.viewport
                    self._clear_active_field()
                    return self.refresh()
                return self._back_or_parent()

        if self.pager is not None:
            if name == "SUITE":
                if self.pager.page_count:
                    self.pager = self.pager.next(wrap=True)
                    self.pagers[self.current.number] = self.pager
                    self._clear_active_field()
                    return self.refresh()
                return Action()
            if name == "RETOUR":
                if self.pager.page_index > 0:
                    self.pager = self.pager.prev()
                    self.pagers[self.current.number] = self.pager
                    self._clear_active_field()
                    return self.refresh()
                return self._back_or_parent()

        if name == "RETOUR":
            return self._back_or_parent()

        ctx = PageContext(self, self.current, self.registry)
        result = self.current.on_key(ctx, name)
        requested = self._take_screensaver_request()
        if requested is not None:
            return requested
        page = self.resolve_page(result)
        if page is not None:
            return self.navigate(page)
        if name == "GUIDE" and self.guide:
            return self.navigate(self.guide)
        return Action()

    @staticmethod
    def _is_user_input(event):
        return isinstance(
            event, (codec.Text, codec.Enter, codec.Function, codec.Key)
        )

    @staticmethod
    def _is_line_ending_echo(data):
        return data in (b"\n", b"\r\n", b"\n\r")

    def _feed_bytes(self, data):
        if not data:
            return []
        if self.screensaver_active and self._is_line_ending_echo(data):
            return []
        events = self.parser.feed(data)
        user_events = [
            event for event in events if self._is_user_input(event)
        ]
        if not user_events:
            return []
        if self.screensaver_active:
            return [self._wake_from_input()]
        self._touch()
        return [self.handle(event) for event in user_events]

    def feed(self, data):
        if not data:
            return []
        actions = []
        for token in self.power.feed(data):
            if isinstance(token, Power):
                if token.on:
                    actions.append(self.resume())
                else:
                    action = self.pause()
                    if action.power is not None:
                        actions.append(action)
                break
            if self.paused:
                actions.append(self.resume())
                break
            actions.extend(self._feed_bytes(token))
        return actions
