"""Transport-neutral session orchestration."""

import time
import traceback
from dataclasses import replace

from ..design.choice import Choice
from ..design.pager import Pager
from ..design.region import PAGE_BACK, MainRegion
from ..design.stops import reveal_viewport
from ..pagemodel.model import PageContext
from ..protocol import codec
from ..render.render import render_diff, reset
from ..render.screen import Screen, resolve_paint
from ..terminal.power import Power, PowerSignals, PowerWatcher
from .action import Action
from ..pagemodel.header import header_requires
from .announcement import AnnouncementMixin
from .editing import EditingMixin
from .header import HeaderMixin
from .idle import IdleMixin
from .navigation import NavigationMixin
from .power import PowerMixin
from .regions import RegionState
from .screensaver import Screensaver


class Session(
    NavigationMixin,
    EditingMixin,
    IdleMixin,
    PowerMixin,
    HeaderMixin,
    AnnouncementMixin,
):
    def __init__(self, registry, profile, *, initial="100", fallback=None,
                 guide=None, echo=False, services=None, screensaver=None,
                 power=None, header=None, announcement_policy=None,
                 clock=time.monotonic, wall_clock=time.time, log=None):
        header_requires(header)
        self.registry = registry
        self.profile = profile
        self.initial = initial
        self.fallback = fallback or registry.get(initial)
        self.guide = guide
        self.echo = echo
        self.header = header
        self.announcement_policy = announcement_policy
        self.log = log or (lambda message: None)
        self.services = dict(services or {})
        self.power_signals = (
            power if isinstance(power, PowerSignals) else PowerSignals()
        )
        self.power = PowerWatcher(self.power_signals)
        self.parser = codec.InputParser()
        self.paused = False
        self.page_error = None
        self._ticks_disabled = set()
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
        self.viewport = None
        self.viewports = {}
        self.stops = None
        self.regions = {}
        self.focused_region = None
        self.requested_focus_region = None
        self.regions_default_focus = None
        self._region_memory = {}
        self._focus_memory = {}
        self._resources = []
        self._closed = False
        self._pager_carousel = None
        self._pager_carousel_next = None
        self._pager_carousel_key = None
        self.screen = None
        self.scroll_mode = False
        self.screen_scroll_mode = False
        self.screen_paint = "row"
        self.screen_header_paint = "row"
        self._shadow_exact = True
        self.clock = clock
        self.wall_clock = wall_clock
        self.status_text = None
        self._body_row = None
        self._header_next = None
        self._last_body_tick = self.clock()
        self._announcement_next = None
        self._announcement_seen = {}
        self._announcement_seeded_channels = set()
        self._announcement_since = self.wall_clock()
        self.announcement = None
        self.announcement_channel = None
        self._announcement_source_page = None
        self._announcement_started = None
        self._announcement_show_until = None
        self._announcement_next_show = None
        self._announcement_queue = []
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

    @property
    def pager(self):
        """The main-region pager, or None."""
        main = self.regions.get("main")
        if main is not None and isinstance(main.cursor, Pager):
            return main.cursor
        return None

    @property
    def choice(self):
        """The main-region Choice, or None."""
        main = self.regions.get("main")
        if main is not None and isinstance(main.cursor, Choice):
            return main.cursor
        return None

    def _touch(self):
        now = self.clock()
        self.last_activity = now
        if self._pager_carousel is not None and self._pager_carousel.active:
            self._pager_carousel_next = now + self._pager_carousel.hold

    def _clear_page_error(self):
        self.page_error = None

    def _clear_page_cursors(self):
        self.fields = []
        self.values = {}
        self.active = 0
        self.active_name = None
        self.requested_focus = None
        self.viewport = None
        self.stops = None

    def _error_screen(self):
        screen = Screen()
        screen.force_full = True
        screen.text(0, 0, "PAGE ERROR", inverse=True)
        screen.text(2, 0, "THIS PAGE COULD NOT BE SHOWN.")
        screen.text(4, 0, "RETOUR=BACK  SOMMAIRE=HOME")
        screen.set_cursor(codec.ROWS - 1, 0, False)
        return screen

    def _render_error(self):
        self.scroll_mode = False
        self.status_text = None
        self.screen_paint = "full"
        self.screen_header_paint = "full"
        self.screen_scroll_mode = False
        self._shadow_exact = True
        self.screen = self._error_screen()
        return self.screen

    def _fail_page(self, where, *, disable_tick=False):
        try:
            self.log(
                f"page error ({where}) on {self.current.number}:\n"
                + traceback.format_exc().rstrip()
            )
        except Exception:
            pass
        self.page_error = where
        if disable_tick:
            self._ticks_disabled.add(self.current.number)
        self._clear_page_cursors()
        self.screensaver_active = False
        self._pager_carousel = None
        self._pager_carousel_next = None
        return self._render_error()

    def _init_page_regions(self):
        definitions = tuple(getattr(self.current, "regions", ()) or ())
        if not definitions:
            self.regions = {}
            self.focused_region = self._focus_memory.get(
                self.current.number
            )
            self.regions_default_focus = None
            return
        self.regions = {
            definition.name: RegionState(
                definition,
                None,
                None,
                (),
                None,
                None,
                None,
                True,
            )
            for definition in definitions
        }
        self.regions_default_focus = (
            getattr(self.current, "default_focus", None)
            or definitions[0].name
        )
        remembered = self._focus_memory.get(self.current.number)
        self.focused_region = (
            remembered
            if remembered in self.regions
            else self.regions_default_focus
        )

    def _adopt_named_regions(self, ctx):
        page_key = self.current.number
        previous = self.regions
        regions = {}
        for name in ctx._region_order:
            definition = ctx._region_defs[name]
            key = ctx._region_keys.get(name)
            cursor = (
                ctx._region_pagers.get(name)
                or ctx._region_choices.get(name)
            )
            enabled = ctx._region_enabled.get(name, True)
            if isinstance(cursor, Pager):
                if ctx._region_pager_explicit.get(name):
                    cursor = cursor.clamp()
                elif (
                    name in previous
                    and previous[name].key == key
                    and previous[name].cursor is not None
                ):
                    cursor = replace(
                        cursor, offset=previous[name].cursor.offset
                    ).clamp()
                else:
                    remembered = self._region_memory.get(
                        (page_key, name, key)
                    )
                    cursor = replace(
                        cursor,
                        offset=(
                            remembered
                            if isinstance(remembered, int) else 0
                        ),
                    ).clamp()
            fields = (
                tuple(ctx.fields)
                if name == ctx._form_region_name
                else ()
            )
            active = enabled and (bool(fields) or cursor is not None)
            if not active and not definition.optional:
                raise ValueError(f"region {name!r} has no cursor")
            committed = (
                previous[name].committed
                if name in previous and previous[name].key == key
                else None
            )
            regions[name] = RegionState(
                definition,
                cursor,
                key,
                fields,
                ctx._region_items.get(name),
                ctx._region_commit.get(name),
                committed,
                active,
                remove=ctx._region_remove.get(name),
                commands=ctx._region_commands.get(name),
            )

        self.regions = regions
        requested = (
            ctx._requested_focus_region or self.requested_focus_region
        )
        if requested not in regions or not regions[requested].active:
            candidates = []
            previous_focus = self._active_target(
                self.focused_region, -1
            )
            if previous_focus not in (None, PAGE_BACK):
                candidates.append(previous_focus)
            remembered = self._focus_memory.get(page_key)
            if remembered in regions and regions[remembered].active:
                candidates.append(remembered)
            default = self._active_target(ctx._default_focus, 1)
            if default not in (None, PAGE_BACK):
                candidates.append(default)
            requested = next(
                (
                    name for name in candidates
                    if name in regions and regions[name].active
                ),
                self._first_active(ctx._default_focus),
            )
        self.focused_region = requested
        self.regions_default_focus = ctx._default_focus
        self.requested_focus_region = None
        if requested is not None:
            self._focus_memory[page_key] = requested
        self._remember_region_offsets()

    def _active_target(self, name, direction):
        seen = set()
        while name not in (None, PAGE_BACK):
            if name in seen:
                return None
            seen.add(name)
            state = self.regions.get(name)
            if state is None:
                return None
            if state.active:
                return name
            name = (
                state.definition.next
                if direction > 0
                else state.definition.prev
            )
        return name

    def _first_active(self, start=None):

        names = list(self.regions)
        if start in self.regions:
            index = names.index(start)
            names = names[index:] + names[:index]
        for name in names:
            if self.regions[name].active:
                return name
        return None

    def _is_pure_pane(self, ctx):
        if self.current.scroll or ctx._viewport_set:
            return False
        fields = tuple(field for field in ctx.fields if not field.ambient)
        return (
            sum(
                (
                    bool(fields),
                    ctx.choice is not None,
                    ctx.pager is not None,
                )
            )
            == 1
        )

    def _adopt_main_region(self, ctx):
        fields = tuple(field for field in ctx.fields if not field.ambient)
        if fields:
            kind = "form"
            cursor = None
            page_size = None
        elif ctx.choice is not None:
            kind = "choice"
            cursor = ctx.choice
            page_size = ctx.choice.pager.page_size
        else:
            kind = "pager"
            cursor = ctx.pager
            page_size = ctx.pager.page_size
        state = self.regions.get("main")
        key = ctx._region_keys.get("main")
        if state is None or state.definition.kind != kind:
            state = RegionState(
                MainRegion(kind, page_size),
                cursor,
                key,
                fields,
                None,
                None,
                None,
                True,
            )
            self.regions = {"main": state}
        else:
            state.definition = MainRegion(kind, page_size)
            state.cursor = cursor
            state.key = key
            state.fields = fields
            state.items = None
            state.commit = None
            state.committed = None
            state.remove = None
            state.commands = None
            state.active = True
        self.focused_region = "main"
        self.regions_default_focus = "main"
        self.requested_focus_region = None
        self._focus_memory[self.current.number] = "main"
        if kind == "pager":
            self._adopt_pager_carousel(cursor, ctx.pager_carousel)
        else:
            self._clear_pager_carousel()
        self._remember_region_offsets()

    def _adopt_region_tick(self, ctx):
        for name in ctx._region_order:
            state = self.regions.get(name)
            if state is None:
                raise ValueError("a page tick cannot change regions")
            previous_key = state.key
            definition = ctx._region_defs[name]
            key = ctx._region_keys.get(name)
            cursor = (
                ctx._region_pagers.get(name)
                or ctx._region_choices.get(name)
            )
            if isinstance(cursor, Pager):
                if ctx._region_pager_explicit.get(name):
                    cursor = cursor.clamp()
                elif state.cursor is not None and state.key == key:
                    cursor = replace(
                        cursor, offset=state.cursor.offset
                    ).clamp()
                else:
                    cursor = cursor.clamp()
            fields = (
                tuple(ctx.fields)
                if name == ctx._form_region_name
                else ()
            )
            enabled = ctx._region_enabled.get(name, True)
            active = enabled and (bool(fields) or cursor is not None)
            if not active and not definition.optional:
                raise ValueError(f"region {name!r} has no cursor")
            state.definition = definition
            state.cursor = cursor
            state.key = key
            state.fields = fields
            state.items = ctx._region_items.get(name)
            state.commit = ctx._region_commit.get(name)
            state.remove = ctx._region_remove.get(name)
            state.commands = ctx._region_commands.get(name)
            state.active = active
            if previous_key != key:
                state.committed = None
        if (
            self.focused_region not in self.regions
            or not self.regions[self.focused_region].active
        ):
            candidates = []
            previous_focus = self._active_target(
                self.focused_region, -1
            )
            if previous_focus not in (None, PAGE_BACK):
                candidates.append(previous_focus)
            remembered = self._focus_memory.get(self.current.number)
            if (
                remembered in self.regions
                and self.regions[remembered].active
            ):
                candidates.append(remembered)
            default = self._active_target(
                self.regions_default_focus, 1
            )
            if default not in (None, PAGE_BACK):
                candidates.append(default)
            self.focused_region = next(
                (
                    name for name in candidates
                    if name in self.regions
                    and self.regions[name].active
                ),
                self._first_active(self.regions_default_focus),
            )
        self._remember_region_offsets()

    def _remember_region_offsets(self):
        page_key = self.current.number
        for name, state in self.regions.items():
            cursor = state.cursor
            if cursor is None:
                continue
            if isinstance(cursor, Choice):
                remembered = (cursor.offset, cursor.selected)
            else:
                remembered = cursor.offset
            self._region_memory[
                (page_key, name, state.key)
            ] = remembered
        while len(self._region_memory) > 64:
            self._region_memory.pop(next(iter(self._region_memory)))
        while len(self._focus_memory) > 32:
            self._focus_memory.pop(next(iter(self._focus_memory)))

    def _form_region_name(self):
        for name, state in self.regions.items():
            if state.is_form and state.active:
                return name
        return None

    def _named_form_focused(self):
        if not self.regions:
            return True
        form = self._form_region_name()
        return form is not None and self.focused_region == form

    def _focus_region(self, name):
        if name not in self.regions or not self.regions[name].active:
            return Action()
        self.focused_region = name
        self.requested_focus_region = None
        self._focus_memory[self.current.number] = name
        return self.refresh()

    def _region_edge(self, region, direction):
        target = (
            region.definition.next
            if direction > 0
            else region.definition.prev
        )
        if target not in (None, PAGE_BACK):
            target = self._active_target(target, direction)
        if target == PAGE_BACK and direction < 0:
            hook = getattr(self.current, "on_back", None)
            if callable(hook):
                ctx = PageContext(self, self.current, self.registry)
                try:
                    handled = hook(ctx)
                except Exception:
                    return Action(screen=self._fail_page("back"))
                if handled:
                    return self.refresh()
            return self._back_or_parent()
        if target is not None:
            return self._focus_region(target)
        if direction < 0:
            return self._back_or_parent()
        return Action()

    def _step_region(self, region, direction):
        if region.is_form:
            if direction > 0:
                if self.active + 1 < len(self.fields):
                    self.active += 1
                    self.active_name = self.fields[self.active].name
                    return self.refresh()
                return self._region_edge(region, direction)
            if self.active > 0:
                self.active -= 1
                self.active_name = self.fields[self.active].name
                return self.refresh()
            return self._region_edge(region, direction)

        cursor = region.cursor
        if cursor is None:
            return self._region_edge(region, direction)
        if isinstance(cursor, Choice):
            moved = (
                cursor.next() if direction > 0 else cursor.prev()
            )
        else:
            wrap = (
                getattr(region.definition, "wrap", False)
                and direction > 0
            )
            moved = (
                cursor.next(wrap=wrap)
                if direction > 0
                else cursor.prev(wrap=wrap)
            )
        if moved == cursor:
            return self._region_edge(region, direction)
        region.cursor = moved
        self._clear_ambient_field()
        self._remember_region_offsets()
        return self.refresh()

    def _function_regions(self, name):
        region = self.regions.get(self.focused_region)
        if region is None:
            return Action()
        if name == "CORRECTION":
            if region.is_form:
                return self.correction()
            if self._ambient_field() is not None:
                return self.correction()
        if name == "ANNULATION":
            if region.is_form:
                return self.annulation()
            ambient = self._ambient_field()
            if ambient is not None and self.values.get(ambient.name):
                return self.annulation()
            if isinstance(region.cursor, Choice) and region.remove is not None:
                selected = region.cursor.selected
                if selected is None:
                    return Action()
                if region.items is not None:
                    if not 0 <= selected < len(region.items):
                        return Action()
                    target = region.items[selected]
                else:
                    target = region.cursor
                try:
                    region.remove(target)
                except Exception:
                    return Action(screen=self._fail_page("remove"))
                return self.refresh()
            if ambient is not None:
                return self.annulation()
            return Action()
        if name == "SUITE":
            return self._step_region(region, 1)
        if name == "RETOUR":
            return self._step_region(region, -1)

        ctx = PageContext(self, self.current, self.registry)
        try:
            result = self.current.on_key(ctx, name)
        except Exception:
            return Action(screen=self._fail_page("key"))
        requested = self._take_screensaver_request()
        if requested is not None:
            return self.screensaver(requested)
        if result == "screensaver":
            return self.screensaver(self.current.screensaver)
        if result is not None:
            return self.navigate(result)
        if name == "GUIDE" and self.guide:
            return self.navigate(self.guide)
        return self.refresh()

    def _activate_region(self):
        region = self.regions.get(self.focused_region)
        if region is None:
            return Action()
        if region.is_form:
            return self.submit()
        if isinstance(region.cursor, Choice) and region.items is not None:
            try:
                selected = region.cursor.selected
                if (
                    selected is not None
                    and 0 <= selected < len(region.items)
                ):
                    item = region.items[selected]
                    region.committed = (
                        region.commit(item)
                        if region.commit is not None
                        else item
                    )
                else:
                    region.committed = None
            except Exception:
                return Action(screen=self._fail_page("commit"))
        elif region.commit is not None:
            try:
                region.committed = region.commit(region.cursor)
            except Exception:
                return Action(screen=self._fail_page("commit"))
        if region.definition.activate == "stay":
            return self.refresh()
        return self.submit()

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
        self.viewport = None
        self.stops = None
        self.regions = {}
        self.focused_region = None
        self.requested_focus_region = None
        self.regions_default_focus = None
        self._clear_pager_carousel()
        self.status_text = None
        self._last_body_tick = self.clock()

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

    def _clear_pager_carousel(self):
        self._pager_carousel = None
        self._pager_carousel_next = None
        self._pager_carousel_key = None

    def _adopt_pager_carousel(self, pager, carousel):
        key = (pager.page_size, pager.offset, carousel)
        allowed = (
            carousel.allowed(pager.page_count)
            if carousel is not None and carousel.active
            else ()
        )
        needs_carousel = bool(allowed) and (
            len(allowed) >= 2 or pager.page_index not in allowed
        )
        if (
            key != self._pager_carousel_key
            or not needs_carousel
            or self._pager_carousel_next is None
        ):
            self._pager_carousel_key = key
            self._pager_carousel = carousel
            if needs_carousel:
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
        self._clear_page_error()
        self._ticks_disabled = set()
        self.parser = self._new_parser()
        self.power = self._new_power()
        self.screensaver_active = False
        self._extension_pending = False
        self.regions = {}
        self.focused_region = None
        self.requested_focus_region = None
        self.regions_default_focus = None
        self._region_memory = {}
        self._focus_memory = {}
        self._last_body_tick = self.clock()
        self._reset_announcement_baseline()
        self._reschedule_announcements(self.clock(), immediate=True)
        self._touch()
        self._shadow_exact = True
        self._init_page_regions()
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
            or self.screen_paint == "full"
        ):
            self._shadow_exact = True
            return Action(screen=new)
        paint = self.screen_paint
        header_paint = self.screen_header_paint
        if not self._shadow_exact:
            paint = "row"
            header_paint = "row"
        return Action(
            raw=render_diff(
                old,
                new,
                scroll=self.scroll_mode,
                paint=paint,
                header_paint=header_paint,
            )
        )

    def render(self):
        if self.page_error is not None:
            return self._render_error()
        self.scroll_mode = bool(self.current.scroll)
        try:
            ctx = PageContext(self, self.current, self.registry)
            screen = self.current.render(ctx)
            self._extension_pending = False
            if not isinstance(screen, Screen):
                raise TypeError(
                    f"page {self.current.number!r} returned "
                    f"{type(screen)!r}, expected Screen"
                )
            self.status_text = ctx.status
            if ctx._viewport_set and ctx.pager is not None:
                raise ValueError(
                    f"page {self.current.number!r} cannot declare both a "
                    "viewport and a pager"
                )
            if ctx._choice_set and (ctx._viewport_set or ctx.pager is not None):
                raise ValueError(
                    f"page {self.current.number!r} cannot mix a choice with "
                    "a viewport or pager"
                )
            if self.current.form and ctx.fields and ctx.pager is not None:
                raise ValueError(
                    f"page {self.current.number!r} cannot declare both form "
                    "fields and a pager"
                )
            if self.current.form and ctx.fields and ctx._viewport_set:
                raise ValueError(
                    f"page {self.current.number!r} cannot declare both form "
                    "fields and a viewport"
                )
            if self.current.form and ctx.fields and ctx._choice_set:
                raise ValueError(
                    f"page {self.current.number!r} cannot declare both form "
                    "fields and a choice"
                )
            ambient = [field for field in ctx.fields if field.ambient]
            form_fields = [field for field in ctx.fields if not field.ambient]
            if len(ambient) > 1:
                raise ValueError(
                    f"page {self.current.number!r} cannot declare more than "
                    "one ambient input"
                )
            if ambient and form_fields:
                raise ValueError(
                    f"page {self.current.number!r} cannot mix an ambient "
                    "input with form fields"
                )
            if ambient and any(ctx._region_commands.values()):
                raise ValueError(
                    f"page {self.current.number!r} cannot mix an ambient "
                    "input with choice commands"
                )
            if form_fields and (
                ctx.pager is not None
                or ctx.choice is not None
                or ctx._viewport_set
            ):
                raise ValueError(
                    f"page {self.current.number!r} cannot mix form fields "
                    "with a pager, choice, or viewport"
                )
            if ctx._regions_declared:
                self._adopt_named_regions(ctx)
                self.viewport = None
                self.stops = None
                self._clear_pager_carousel()
            elif self._is_pure_pane(ctx):
                self._adopt_main_region(ctx)
                self.viewport = None
                self.stops = None
            else:
                self.regions = {}
                self.focused_region = None
                self.requested_focus_region = None
                self.regions_default_focus = None
                self._adopt_viewport(
                    ctx.viewport if ctx._viewport_set else None
                )
                self.stops = ctx.stops if ctx._stops_set else None
                self._clear_pager_carousel()
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
            if (
                ctx._regions_declared
                and not self._named_form_focused()
                and self._ambient_field() is None
            ):
                screen.set_cursor(codec.ROWS - 1, 0, False)
            elif field is not None and field.visible:
                value = self.values.get(field.name, "")
                col = field.col + min(len(value), field.width)
                screen.set_cursor(field.row, col, self._cursor_visible())
            else:
                screen.set_cursor(codec.ROWS - 1, 0, False)
            self.screen_paint = resolve_paint(
                getattr(self.current, "paint", None),
                screen.paint,
                allow_full=True,
                what="page paint",
            )
        except (KeyError, ValueError, TypeError):
            raise
        except Exception:
            return self._fail_page("render")
        try:
            screen = self._compose_header(screen, self.current)
        except (KeyError, ValueError, TypeError):
            raise
        except Exception:
            return self._fail_page("header")
        self._clear_page_error()
        self.screen = screen
        self.screen_scroll_mode = self.scroll_mode
        return screen

    def tick(self):
        if self.paused or self.page_error is not None:
            return Action()
        try:
            return self._tick_page()
        except Exception:
            return Action(
                screen=self._fail_page("tick", disable_tick=True)
            )

    def _tick_page(self):
        if self.paused:
            return Action()
        self._last_body_tick = self.clock()
        page = self.display_page
        self.scroll_mode = bool(page.scroll)
        if self.screensaver_active:
            if self._page_tick_interval(page, pause_on_input=False) is None:
                return Action()
        elif self.next_tick_delay() is None:
            return Action()
        ctx = PageContext(self, page, self.registry, tick=True)
        frame = page.on_tick(ctx)
        if ctx.status is not None:
            self.status_text = ctx.status
        if not self.screensaver_active and ctx._regions_declared:
            self._adopt_region_tick(ctx)
        elif not self.screensaver_active and self._is_pure_pane(ctx):
            self._adopt_main_region(ctx)
        elif not self.screensaver_active:
            self.regions = {}
            self.focused_region = None
            self.requested_focus_region = None
            self.regions_default_focus = None
            if ctx._viewport_set:
                self._adopt_viewport(ctx.viewport)
            if ctx._stops_set:
                self.stops = ctx.stops
            self._clear_pager_carousel()
        if frame is None:
            return Action()
        if isinstance(frame, (bytes, bytearray)):
            frame = bytes(frame)
            if frame:
                self._shadow_exact = False
                frame = reset() + frame
            if not self.screensaver_active and frame and self.active_field is not None:
                frame += self._focus_frame()
            return Action(raw=frame)
        if isinstance(frame, Screen):
            if self.screensaver_active:
                frame.set_cursor(codec.ROWS - 1, 0, False)
            elif (
                ctx._regions_declared
                and not self._named_form_focused()
                and self._ambient_field() is None
            ):
                frame.set_cursor(codec.ROWS - 1, 0, False)
            else:
                field = self.active_field
                if field is not None and field.visible:
                    value = self.values.get(field.name, "")
                    col = field.col + min(len(value), field.width)
                    frame.set_cursor(field.row, col, self._cursor_visible())
                else:
                    frame.set_cursor(codec.ROWS - 1, 0, False)
            self.screen_paint = resolve_paint(
                getattr(page, "paint", None),
                frame.paint,
                allow_full=True,
                what="page paint",
            )
            frame = self._compose_header(frame, page)
            old = self.screen
            if (
                old is None
                or self.scroll_mode != self.screen_scroll_mode
                or getattr(frame, "force_full", False)
                or self.screen_paint == "full"
            ):
                self.screen = frame
                self.screen_scroll_mode = self.scroll_mode
                self._shadow_exact = True
                return Action(screen=frame)
            paint = self.screen_paint
            header_paint = self.screen_header_paint
            if not self._shadow_exact:
                paint = "row"
                header_paint = "row"
            diff = render_diff(
                old,
                frame,
                scroll=self.scroll_mode,
                paint=paint,
                header_paint=header_paint,
            )
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
        if self.page_error is not None:
            if (
                isinstance(event, codec.Function)
                and event.name in ("RETOUR", "SOMMAIRE")
            ):
                return self.function(event.name)
            if isinstance(event, codec.Text):
                return Action(raw=bytes([codec.BEL]))
            return Action()
        self._touch()
        if isinstance(event, codec.Text):
            return self.text_event(event)
        if isinstance(event, codec.Enter):
            if self.regions:
                if self._ambient_pending():
                    return self.submit()
                return self._activate_region()
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
            try:
                result = self.current.on_key(ctx, event.name)
            except Exception:
                return Action(screen=self._fail_page("key"))
            requested = self._take_screensaver_request()
            if requested is not None:
                return requested
            page = self.resolve_page(result)
            if page is not None:
                return self.navigate(page)
            return Action()
        return Action()

    def function(self, name):
        if self.page_error is not None:
            if name == "SOMMAIRE":
                return self.home()
            if name == "RETOUR":
                return self._back_or_parent()
            return Action()

        if name == "ENVOI":
            if self.regions:
                return self._activate_region()
            return self.submit()

        if name == "SOMMAIRE":
            return self.home()

        if self.regions:
            return self._function_regions(name)

        if name == "CORRECTION":
            return self.correction()

        if name == "ANNULATION":
            return self.annulation()

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

        if name == "RETOUR":
            return self._back_or_parent()

        ctx = PageContext(self, self.current, self.registry)
        try:
            result = self.current.on_key(ctx, name)
        except Exception:
            return Action(screen=self._fail_page("key"))
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
        transitioned = False
        for token in self.power.feed(data):
            if isinstance(token, Power):
                transitioned = True
                if token.on:
                    actions.append(self.resume())
                else:
                    action = self.pause()
                    if action.power is not None:
                        actions.append(action)
                continue
            if transitioned:
                continue
            if self.paused:
                actions.append(self.resume())
                continue
            actions.extend(self._feed_bytes(token))
        return actions
