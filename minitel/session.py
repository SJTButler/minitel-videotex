"""Transport-neutral session: input, navigation, history, and page rendering."""

import time
from dataclasses import dataclass, replace

from . import codec
from .pages import Page, PageContext
from .power import Power, PowerSignals, PowerWatcher
from .render import render_diff, reset
from .screen import Screen
from .screensaver import Screensaver


@dataclass
class Action:
    raw: bytes = b""
    screen: Screen | None = None
    page: Page | None = None
    power: bool | None = None


class Session:
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
        self.fields = []
        self.values = {}
        self.active = 0
        self.active_name = None
        self.requested_focus = None
        self.pager = None
        self.pagers = {}
        self._resources = []
        self._closed = False
        self._pager_carousel = None
        self._pager_carousel_next = None
        self._pager_carousel_key = None
        self.screen = None
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

    @property
    def active_field(self):
        if not self.fields:
            return None
        index = max(0, min(self.active, len(self.fields) - 1))
        return self.fields[index]

    @property
    def input(self):
        return self.active_field

    @property
    def line(self):
        field = self.active_field
        return self.values.get(field.name, "") if field else ""

    @line.setter
    def line(self, value):
        field = self.active_field
        if field is not None:
            self.values[field.name] = value

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

    def _has_input_text(self):
        return any(self.values.get(field.name, "") for field in self.fields)

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

    def _clear_active_field(self):
        field = self.active_field
        if field is not None:
            self.values[field.name] = ""

    def _cursor_visible(self):
        field = self.active_field
        if field is None:
            return False
        if field.cursor == "auto":
            return bool(self.values.get(field.name, ""))
        return field.cursor == "visible"

    def _focus_frame(self):
        field = self.active_field
        if field is None:
            return b""
        value = self.values.get(field.name, "")
        col = field.col + min(len(value), field.width)
        raw = bytearray(codec.pos(field.row, col))
        raw += codec.cursor(self._cursor_visible())
        if self.screen is not None:
            cell = self.screen.rows[field.row][field.col]
            raw += codec.inverse(cell.inverse)
        return bytes(raw)

    def _shadow_put(self, field, index, char):
        if self.screen is None:
            return
        row = field.row
        col = field.col + index
        if not (0 <= row < codec.ROWS and 0 <= col < codec.COLS):
            return
        base = self.screen.rows[row][field.col]
        self.screen.rows[row][col] = replace(base, ch=char)

    def _sync_shadow_cursor(self):
        field = self.active_field
        if field is None or self.screen is None:
            return
        value = self.values.get(field.name, "")
        col = field.col + min(len(value), field.width)
        self.screen.set_cursor(field.row, col, self._cursor_visible())

    def start(self):
        self.paused = False
        self.parser = self._new_parser()
        self.power = self._new_power()
        self.screensaver_active = False
        self._touch()
        return self.render()

    def refresh(self):
        if self.paused:
            return Action()
        old = self.screen
        new = self.render()
        if old is None:
            return Action(screen=new)
        return Action(raw=render_diff(old, new))

    def render(self):
        ctx = PageContext(self, self.current, self.registry)
        screen = self.current.render(ctx)
        if not isinstance(screen, Screen):
            raise TypeError(
                f"page {self.current.number!r} returned {type(screen)!r}, expected Screen"
            )
        self._adopt_pager(ctx.pager, ctx.pager_carousel)
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
        if field is not None:
            value = self.values.get(field.name, "")
            col = field.col + min(len(value), field.width)
            screen.set_cursor(field.row, col, self._cursor_visible())
        else:
            screen.set_cursor(24, 0, False)
        self.screen = screen
        return screen

    def resolve_page(self, value):
        if isinstance(value, Page):
            return value
        if isinstance(value, str):
            return self.registry.get(value)
        return None

    def navigate(self, value, *, push=True):
        self.screensaver_active = False
        self._touch()
        page = self.resolve_page(value)
        if page is None:
            page = self.fallback
        if page is not self.current:
            if push:
                if self.current.transient:
                    if self.history and self.history[-1] is page:
                        self.history.pop()
                else:
                    self.history.append(self.current)
            self._reset_page()
        self.current = page
        return Action(screen=self.render(), page=page)

    def submit(self):
        line = self.line.strip()
        self.last_key = line
        ctx = PageContext(self, self.current, self.registry)
        values = dict(self.values)
        if callable(self.current.on_form):
            result = self.current.on_form(ctx, values)
        else:
            result = self.current.on_submit(ctx, line)
        requested = self._take_screensaver_request()
        if requested is not None:
            return requested
        page = self.resolve_page(result)
        if page is None and not self.current.form:
            page = self.registry.get(line)
        if page is None:
            page = self.fallback
        return self.navigate(page)

    def _back_or_parent(self):
        target = self.resolve_page(self.current.back_page)
        if (
            target is not None
            and target.number != self.current.number
            and (not self.history or self.history[-1].number != target.number)
        ):
            return self.navigate(target, push=False)
        return self.back()

    def back(self):
        self.screensaver_active = False
        self._touch()
        if self.history:
            self.current = self.history.pop()
        else:
            self.current = self.registry.resolve(self.initial)
        self._reset_page()
        return Action(screen=self.render(), page=self.current)

    def home(self):
        self.screensaver_active = False
        self._touch()
        self.history.clear()
        self.current = self.registry.resolve(self.initial)
        self._reset_page()
        return Action(screen=self.render(), page=self.current)

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

    def pause(self):
        if self.paused:
            return Action()
        self.paused = True
        self.parser = self._new_parser()
        self.power.reset()
        return Action(power=False)

    def resume(self):
        now = self.clock()
        self.paused = False
        self.parser = self._new_parser()
        self.power.reset()
        self._touch()
        if self.screensaver_active:
            self._screensaver_since = now
            action = self._render_screensaver()
        else:
            action = Action(screen=self.render())
        action.raw = self.echo_override() + action.raw
        action.power = True
        return action

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

    def tick(self):
        if self.paused:
            return Action()
        page = self.display_page
        if self.screensaver_active:
            if self._page_tick_interval(page, pause_on_input=False) is None:
                return Action()
        elif self.next_tick_delay() is None:
            return Action()
        ctx = PageContext(self, page, self.registry)
        frame = page.on_tick(ctx)
        if not self.screensaver_active and ctx.pager is not None:
            self._adopt_pager(ctx.pager, ctx.pager_carousel)
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
                if field is not None:
                    value = self.values.get(field.name, "")
                    col = field.col + min(len(value), field.width)
                    frame.set_cursor(field.row, col, self._cursor_visible())
                else:
                    frame.set_cursor(codec.ROWS - 1, 0, False)
            old = self.screen
            if old is None:
                self.screen = frame
                return Action(screen=frame)
            diff = render_diff(old, frame)
            self.screen = frame
            return Action(raw=diff)
        raise TypeError(
            f"page {page.number!r} tick returned {type(frame)!r}; "
            "expected bytes, Screen, or None"
        )

    def handle(self, event):
        if self.screensaver_active:
            return self._wake_from_input()
        self._touch()
        if isinstance(event, codec.Text):
            field = self.active_field
            if field is None:
                return Action(raw=bytes([codec.BEL]))
            value = self.values.get(field.name, "")
            if len(value) >= field.width:
                return Action(raw=bytes([codec.BEL]))
            prefix = b""
            if field.cursor == "auto" and not value:
                prefix = codec.cursor(True)
            echo = b""
            if self.echo:
                if self.screen is not None:
                    base = self.screen.rows[field.row][field.col]
                    prefix += codec.inverse(base.inverse)
                echo = codec.text(event.char)
            self._shadow_put(field, len(value), event.char)
            self.values[field.name] = value + event.char
            self._sync_shadow_cursor()
            return Action(raw=prefix + echo)
        if isinstance(event, codec.Enter):
            return self.submit()
        if isinstance(event, codec.Function):
            return self.function(event.name)
        if isinstance(event, codec.Key):
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
            field = self.active_field
            value = self.values.get(field.name, "") if field else ""
            if field and value:
                value = value[:-1]
                self.values[field.name] = value
                self._shadow_put(field, len(value), " ")
                self._sync_shadow_cursor()
                raw = bytes([codec.BS, 0x20, codec.BS])
                if field.cursor == "auto" and not value:
                    raw += codec.cursor(False)
                return Action(raw=raw)
            return Action()

        if name == "ANNULATION":
            field = self.active_field
            if field:
                self.values[field.name] = ""
            return self.refresh()

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

    def _feed_bytes(self, data):
        if not data:
            return []
        if self.screensaver_active:
            return [self._wake_from_input()]
        events = self.parser.feed(data)
        self._touch()
        return [self.handle(event) for event in events]

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
