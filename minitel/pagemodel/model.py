"""Page API, page context, and registry."""

import importlib
import pkgutil
from dataclasses import dataclass

from ..design.carousel import Carousel
from ..design.choice import Choice
from ..design.field import InputField
from ..design.pager import Pager
from ..design.region import Region, validate_regions
from ..design.stops import Stops
from ..design.viewport import Viewport
from ..protocol import codec
from ..render.screen import Screen, validate_paint
from .announcement import (
    announcement_channel,
    validate_announcement_declaration,
)
from .header import Header, header_requires


CURSOR_MODES = ("visible", "hidden", "auto")
LINE_FIELD = "input"
EXTENSION_SEPARATORS = ("#", "£")
MAX_EXTENSION_LENGTH = 6


def _check_field_placement(row, col, width):
    if not all(isinstance(value, int) for value in (row, col, width)):
        raise TypeError("field row, col, and width must be integers")
    if width < 1:
        raise ValueError("field width must be at least 1")
    if not 0 <= row < codec.ROWS:
        raise ValueError(f"field row must be between 0 and {codec.ROWS - 1}")
    if not 0 <= col < codec.COLS:
        raise ValueError(f"field col must be between 0 and {codec.COLS - 1}")
    if col + width > codec.COLS:
        raise ValueError(
            f"field width {width} at col {col} exceeds {codec.COLS} columns"
        )


@dataclass(frozen=True)
class RegionView:
    name: str
    definition: Region
    cursor: Choice | Pager | None
    focused: bool
    key: object | None
    committed: object | None = None


class PageContext:
    def __init__(self, session, page, registry, *, tick=False):
        self._session = session
        self.page = page
        self.registry = registry
        self._tick = tick
        self._tick_fields = tuple(session.fields) if tick else ()
        self._tick_field_index = 0
        self.fields = []
        self.values = session.values
        self.focus_name = None
        self.pager = None
        self.pager_carousel = None
        self.viewport = session.viewport
        self._viewport_set = False
        self.stops = session.stops
        self._stops_set = False
        self.choice = session.choice
        self._choice_set = False
        self._regions_declared = False
        self._region_defs = {}
        self._region_order = []
        self._region_pagers = {}
        self._region_pager_explicit = {}
        self._region_choices = {}
        self._region_committed = {}
        self._region_items = {}
        self._region_commit = {}
        self._region_keys = {}
        self._region_enabled = {}
        self._form_region_name = None
        self._default_focus = None
        self._requested_focus_region = None
        static_regions = tuple(getattr(page, "regions", ()) or ())
        self._static_regions = bool(static_regions)
        if static_regions:
            self._regions_declared = True
            self._region_defs = {
                region.name: region for region in static_regions
            }
            self._region_order = [region.name for region in static_regions]
            self._default_focus = (
                getattr(page, "default_focus", None)
                or self._region_order[0]
            )
        self.status = None
        self.now = session.wall_clock()

    @property
    def line(self):
        return self._session.line

    @property
    def profile(self):
        return self._session.profile

    @property
    def extension(self):
        return getattr(self.page, "extension", None)

    def take_extension(self):
        """Return the route token once after navigation, else ``None``."""
        token = getattr(self.page, "extension", None)
        if token is None or not self._session._extension_pending:
            return None
        self._session._extension_pending = False
        return token

    @property
    def last_key(self):
        return self._session.last_key

    @property
    def state(self):
        return self._session.state

    def service(self, name, default=None):
        if name not in self.page.requires:
            raise KeyError(
                f"page {self.page.number!r} does not declare service {name!r}"
            )
        return self._session.services.get(name, default)

    def add_resource(self, resource):
        return self._session.add_resource(resource)

    def set_regions(self, *regions, default_focus=None):
        raise ValueError(
            "pane regions are declared statically on @page(regions=...); "
            "bind items, keys, and commits in render(ctx)"
        )

    def region(self, name):
        if self._regions_declared:
            definition = self._region_defs.get(name)
            if definition is None:
                raise KeyError(f"unknown region {name!r}")
            state = self._session.regions.get(name)
            cursor = (
                self._region_pagers.get(name)
                or self._region_choices.get(name)
                or (state.cursor if state is not None else None)
            )
            committed = self._region_committed.get(name)
            if committed is None and state is not None:
                committed = state.committed
            key = self._region_keys.get(name)
            if key is None and state is not None:
                key = state.key
            return RegionView(
                name,
                definition,
                cursor,
                self.focused_region == name,
                key,
                committed,
            )
        state = self._session.regions.get(name)
        if state is None:
            raise KeyError(f"unknown region {name!r}")
        return RegionView(
            name,
            state.definition,
            state.cursor,
            self._session.focused_region == name,
            state.key,
            state.committed,
        )

    @property
    def focused_region(self):
        if self._requested_focus_region is not None:
            return self._requested_focus_region
        if self._regions_declared:
            pending = self._session.requested_focus_region
            if pending in self._region_defs:
                return pending
            current = self._session.focused_region
            if current in self._region_defs:
                return current
            return self._default_focus
        if self._session.regions:
            return self._session.focused_region
        return "main"

    def focus_region(self, name):
        if self._tick:
            raise ValueError("a page tick cannot change region focus")
        if self._regions_declared:
            if name not in self._region_defs:
                raise ValueError(f"unknown region {name!r}")
        elif name not in self._session.regions:
            raise ValueError(f"unknown region {name!r}")
        self._requested_focus_region = name
        self._session.requested_focus_region = name

    @property
    def active_name(self):
        return self._session.requested_focus or self._session.active_name

    def add_field(self, name, row, col, width, *, value="",
                  cursor="visible", live=False, visible=True, region=None):
        if cursor not in CURSOR_MODES:
            raise ValueError(f"cursor must be one of {CURSOR_MODES}")
        if region is not None or self._regions_declared:
            self._claim_form_region(region)
        if self._tick:
            return self._redeclare_tick_field(
                name, row, col, width, value=value, cursor=cursor,
                live=live, visible=visible,
            )
        if self.page.form and self._choice_set:
            raise ValueError(
                f"page {self.page.number!r} cannot declare both form fields "
                "and a choice"
            )
        _check_field_placement(row, col, width)
        if any(field.name == name for field in self.fields):
            raise ValueError(f"duplicate field name {name!r}")
        field = InputField(
            name, row, col, width, value=value, cursor=cursor,
            live=live, visible=visible,
        )
        self.fields.append(field)
        self.values.setdefault(name, value)
        return field

    def _claim_form_region(self, region):
        if not self._regions_declared:
            raise ValueError("page has not declared regions")
        if region is None:
            if not self._static_regions:
                raise ValueError("a named-region page must pass region=")
            candidates = [
                definition.name
                for definition in self._region_defs.values()
                if definition.kind == "form"
            ]
            if len(candidates) != 1:
                raise ValueError("a named-region page must pass region=")
            region = candidates[0]
        if region not in self._region_defs:
            raise ValueError(f"unknown region {region!r}")
        if region in self._region_pagers or region in self._region_choices:
            raise ValueError(f"region {region!r} already has a cursor")
        if (
            self._static_regions
            and self._region_defs[region].kind != "form"
        ):
            raise ValueError(f"region {region!r} is not a form region")
        if not self.page.form:
            raise ValueError("a named form region requires form=True")
        if self._form_region_name not in (None, region):
            raise ValueError(
                "the first slice supports one form region per page"
            )
        self._form_region_name = region

    def _redeclare_tick_field(self, name, row, col, width, **attrs):
        if self._tick_field_index >= len(self._tick_fields):
            raise ValueError(
                "a page tick cannot add input fields"
            )
        existing = self._tick_fields[self._tick_field_index]
        declared = (name, row, col, width,
                    attrs["value"], attrs["cursor"],
                    attrs["live"], attrs["visible"])
        current = (existing.name, existing.row, existing.col, existing.width,
                   existing.value, existing.cursor,
                   existing.live, existing.visible)
        if declared != current:
            raise ValueError(
                "a page tick cannot change input fields"
            )
        self._tick_field_index += 1
        self.fields.append(existing)
        return existing

    @property
    def input_value(self):
        return self.values.get(LINE_FIELD, "")

    def clear_input(self):
        self.values[LINE_FIELD] = ""

    def set_input(self, row, col, width, *, value="",
                  cursor="visible", live=False, visible=True, region=None):
        return self.add_field(
            LINE_FIELD, row, col, width,
            value=value, cursor=cursor, live=live, visible=visible,
            region=region,
        )

    def set_status(self, text):
        if not isinstance(text, str):
            raise TypeError("status must be a string")
        self.status = text

    def set_pager(self, total, page_size=None, *, offset=None, carousel=None,
                  region=None, key=None, items=None, enabled=True):
        if not isinstance(total, int):
            if items is not None:
                raise TypeError("pass either a sequence or items=, not both")
            items = tuple(total)
            total = len(items)
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a bool")
        if region is not None or self._regions_declared:
            return self._set_region_pager(
                region, total, page_size, offset=offset, carousel=carousel,
                key=key, items=items, enabled=enabled,
            )
        if page_size is None:
            raise TypeError("page_size is required on a page without regions")
        if self._viewport_set:
            raise ValueError(
                f"page {self.page.number!r} cannot declare both a viewport "
                "and a pager"
            )
        if self.page.form and self.fields:
            raise ValueError(
                f"page {self.page.number!r} cannot declare both form fields "
                "and a pager"
            )
        if carousel is not None and not isinstance(carousel, Carousel):
            raise TypeError("carousel must be a Carousel or None")
        if offset is None:
            current = self._session.pager
            if current is not None:
                offset = current.offset
            else:
                stored = self._session.pagers.get(self.page.number)
                offset = stored.offset if stored is not None else 0
        self.pager = Pager(total, page_size, offset).clamp()
        self.pager_carousel = carousel
        return self.pager

    def _set_region_pager(self, region, total, page_size, *, offset, carousel,
                          key, items, enabled):
        if not self._regions_declared:
            raise ValueError("page has not declared regions")
        if region is None:
            if not self._static_regions:
                raise ValueError("a named-region page must pass region=")
            candidates = [
                definition.name
                for definition in self._region_defs.values()
                if definition.kind == "pager"
            ]
            if len(candidates) != 1:
                raise ValueError("a named-region page must pass region=")
            region = candidates[0]
        if region not in self._region_defs:
            raise ValueError(f"unknown region {region!r}")
        definition = self._region_defs[region]
        if self._static_regions and definition.kind != "pager":
            raise ValueError(f"region {region!r} is not a pager region")
        if region in self._region_pagers or region in self._region_choices:
            raise ValueError(f"region {region!r} already has a cursor")
        if region == self._form_region_name:
            raise ValueError(f"region {region!r} already has form fields")
        if carousel is not None:
            raise ValueError("carousel regions are not enabled yet")
        if page_size is None:
            page_size = definition.page_size
        if page_size is None:
            raise ValueError(
                f"region {region!r} needs a page_size on @page or set_pager"
            )
        try:
            hash(key)
        except TypeError as exc:
            raise TypeError("region key must be hashable") from exc
        if items is not None:
            items = tuple(items)
            total = len(items)
        explicit = offset is not None
        if offset is None:
            previous = self._session.regions.get(region)
            if (
                previous is not None
                and previous.key == key
                and previous.cursor is not None
            ):
                offset = previous.cursor.offset
            else:
                remembered = self._session._region_memory.get(
                    (self.page.number, region, key)
                )
                offset = remembered if isinstance(remembered, int) else 0
        self._region_pagers[region] = Pager(
            total, page_size, offset or 0
        ).clamp()
        self._region_pager_explicit[region] = explicit
        self._region_keys[region] = key
        self._region_items[region] = (
            tuple(items) if items is not None else None
        )
        self._region_enabled[region] = enabled
        return self._region_pagers[region]

    def _set_region_choice(self, region, total, page_size, *, selected,
                           reset, wrap, key, commit, items, enabled):
        if not self._regions_declared:
            raise ValueError("page has not declared regions")
        if region is None:
            if not self._static_regions:
                raise ValueError("a named-region page must pass region=")
            candidates = [
                definition.name
                for definition in self._region_defs.values()
                if definition.kind == "choice"
            ]
            if len(candidates) != 1:
                raise ValueError("a named-region page must pass region=")
            region = candidates[0]
        if region not in self._region_defs:
            raise ValueError(f"unknown region {region!r}")
        definition = self._region_defs[region]
        if self._static_regions and definition.kind != "choice":
            raise ValueError(f"region {region!r} is not a choice region")
        if region in self._region_pagers or region in self._region_choices:
            raise ValueError(f"region {region!r} already has a cursor")
        if region == self._form_region_name:
            raise ValueError(f"region {region!r} already has form fields")
        if wrap:
            raise ValueError("named choice regions do not support wrap yet")
        if page_size is None:
            page_size = definition.page_size
        if page_size is None:
            raise ValueError(
                f"region {region!r} needs a page_size on @page or set_choice"
            )
        try:
            hash(key)
        except TypeError as exc:
            raise TypeError("region key must be hashable") from exc
        if commit is not None and not callable(commit):
            raise TypeError("region commit must be callable or None")
        if items is not None:
            items = tuple(items)
            total = len(items)
        total = max(0, int(total))
        page_size = max(1, int(page_size))
        previous = self._session.regions.get(region)
        same_key = (
            previous is not None
            and previous.key == key
            and isinstance(previous.cursor, Choice)
        )
        remembered = self._session._region_memory.get(
            (self.page.number, region, key)
        )
        if selected is not None:
            index = selected
            offset = (
                previous.cursor.offset
                if same_key and not reset else 0
            )
        elif reset:
            index = 0 if total else None
            offset = 0
        elif same_key:
            index = previous.cursor.selected
            offset = previous.cursor.offset
        elif isinstance(remembered, tuple) and (
            previous is None or previous.key != key
        ):
            offset, index = remembered
        else:
            index = 0 if total else None
            offset = 0
        choice = Choice(
            Pager(total, page_size, offset), index
        ).clamp()
        self._region_choices[region] = choice
        self._region_keys[region] = key
        self._region_commit[region] = commit
        self._region_items[region] = items
        self._region_enabled[region] = enabled
        if same_key:
            self._region_committed[region] = previous.committed
        return choice

    def set_viewport(self, total, height, *, offset=None, follow=None, step=None):
        if self._regions_declared:
            raise ValueError("named regions do not support viewports")
        if not self.page.scroll:
            raise ValueError(
                f"page {self.page.number!r} must declare scroll=True "
                "to use a viewport"
            )
        if self.pager is not None:
            raise ValueError(
                f"page {self.page.number!r} cannot declare both a pager "
                "and a viewport"
            )
        if self.page.form and self.fields:
            raise ValueError(
                f"page {self.page.number!r} cannot declare both form fields "
                "and a viewport"
            )
        stored = self._session.viewports.get(self.page.number)
        base = self.viewport if self.viewport is not None else stored
        requested_offset = offset
        if offset is None:
            offset = base.offset if base is not None else 0
        if follow is None:
            follow = base.follow if base is not None else False
        if step is None:
            step = base.step if base is not None else 1
        if requested_offset is None and follow:
            offset = max(0, total - height)
        self.viewport = Viewport(
            total, height, offset, follow, step
        ).clamp()
        self._viewport_set = True
        return self.viewport

    def set_stops(self, stops, *, start_next=0, start_prev=0,
                  selected=None, reset=False, wrap=True):
        if self._regions_declared:
            raise ValueError("named regions do not support viewports")
        if not self._viewport_set:
            raise ValueError(
                f"page {self.page.number!r} must set a viewport before stops"
            )
        stops = tuple(stops)
        for stop in stops:
            if not hasattr(stop, "first_line") or not hasattr(stop, "link"):
                raise TypeError("stops must be Stop values")
        current = self.stops
        identity = tuple(
            (stop.first_line, stop.link) for stop in stops
        )
        if reset or current is None or current.identity != identity:
            selected = None
        elif selected is None:
            selected = current.selected
        self.stops = Stops(
            stops, selected, start_next, start_prev, wrap
        ).clamp()
        self._stops_set = True
        return self.stops

    def set_choice(self, total, page_size=None, *, selected=None, reset=False,
                   wrap=False, region=None, key=None, commit=None, items=None,
                   enabled=True):
        if not isinstance(total, int):
            if items is not None:
                raise TypeError("pass either a sequence or items=, not both")
            items = tuple(total)
            total = len(items)
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a bool")
        if region is not None or self._regions_declared:
            return self._set_region_choice(
                region, total, page_size,
                selected=selected, reset=reset, wrap=wrap,
                key=key, commit=commit, items=items, enabled=enabled,
            )
        if page_size is None:
            raise TypeError("page_size is required on a page without regions")
        if self._viewport_set or self.pager is not None:
            raise ValueError(
                f"page {self.page.number!r} cannot mix a choice with "
                "a viewport or pager"
            )
        if self.page.form and self.fields:
            raise ValueError(
                f"page {self.page.number!r} cannot mix form fields with "
                "a choice"
            )
        total = max(0, int(total))
        page_size = max(1, int(page_size))
        current = self.choice
        if selected is not None:
            index = selected
        elif (
            reset or current is None or current.total != total
            or current.page_size != page_size
        ):
            index = 0 if total else None
        else:
            index = current.selected
        self.choice = Choice(
            Pager(total, page_size), index, wrap
        ).clamp()
        self._choice_set = True
        return self.choice

    @property
    def screensaver(self):
        return self._session.screensaver

    @property
    def idle_elapsed(self):
        return self._session.idle_elapsed

    def set_screensaver(self, pages, *, after=120.0, hold=20.0, wrap=True):
        return self._session.set_screensaver(
            pages, after=after, hold=hold, wrap=wrap
        )

    def disable_screensaver(self):
        return self._session.disable_screensaver()

    def start_screensaver(self, index=0):
        return self._session.request_screensaver(index)

    def field(self, name):
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def focus(self, name):
        if self._tick:
            raise ValueError("a page tick cannot change field focus")
        self._session.requested_focus = name

    def page_for(self, key):
        return self.registry.get(key)


class Page:
    number = ""
    title = ""
    aliases = ()
    meta = {}
    form = False
    transient = False
    back_page = None
    extension_back_page = None
    screensaver = None
    no_screensaver = False
    scroll = False
    paint = None
    tick_interval = None
    on_form = None
    on_back = None
    requires = ()
    extensions = False
    header = None
    announce = None
    announce_channel = None
    regions = ()
    default_focus = None

    def render(self, ctx: PageContext) -> Screen:
        raise NotImplementedError

    def on_submit(self, ctx: PageContext, line: str):
        return None

    def on_key(self, ctx: PageContext, key: str):
        return None

    def on_tick(self, ctx):
        return None

    def on_back(self, ctx):
        return None

    def matches(self, key: str) -> bool:
        return key == self.number or key in self.aliases


class FunctionPage(Page):
    def __init__(self, number, render, *, title="", aliases=(), on_submit=None,
                 on_key=None, on_tick=None, tick_interval=None, form=False,
                 on_form=None, on_back=None, transient=False, back_page=None,
                 extension_back_page=None, screensaver=None,
                 no_screensaver=False, scroll=False, paint=None, requires=(),
                 extensions=False, header=None, announce=None,
                 announce_channel=None, meta=None, regions=(),
                 default_focus=None):
        if screensaver is not None and (
            not isinstance(screensaver, str) or not screensaver
        ):
            raise TypeError("screensaver must be a non-empty string or None")
        if isinstance(requires, str) or any(
            not isinstance(key, str) or not key.strip()
            for key in requires
        ):
            raise TypeError("requires must be a sequence of service keys")
        requires = tuple(key.strip() for key in requires)
        if header is not None and header is not False:
            if not isinstance(header, Header):
                raise TypeError(
                    "header must be None, False, or a Header instance"
                )
            header_requires(header)
        announce_channel = validate_announcement_declaration(
            announce, announce_channel
        )
        self.announce = announce
        self.announce_channel = announce_channel
        self.header = header
        self.number = number
        self._render = render
        self.defined_in = getattr(render, "__module__", "")
        self.title = title
        self.aliases = tuple(aliases)
        self.requires = requires
        self.back_page = back_page
        self.extension_back_page = extension_back_page
        self.screensaver = screensaver or None
        self.no_screensaver = bool(no_screensaver)
        self.scroll = bool(scroll)
        self.paint = validate_paint(
            paint, allow_full=True, what="page paint"
        )
        self.extensions = bool(extensions)
        self._on_submit = on_submit
        self._on_key = on_key
        self._on_tick = on_tick
        self.tick_interval = tick_interval
        self.form = form
        self.on_form = on_form
        if on_back is not None:
            self.on_back = on_back
        self.transient = transient
        self.meta = dict(meta or {})
        self.regions = tuple(regions)
        self.default_focus = default_focus
        validate_regions(
            self.regions,
            default_focus=self.default_focus,
            form=self.form,
            scroll=self.scroll,
        )

    def render(self, ctx):
        return self._render(ctx)

    def on_submit(self, ctx, line):
        if self._on_submit:
            return self._on_submit(ctx, line)
        return None

    def on_key(self, ctx, key):
        if self._on_key:
            return self._on_key(ctx, key)
        return None

    def on_tick(self, ctx):
        if self._on_tick:
            return self._on_tick(ctx)
        return None


class ExtensionPage(Page):
    """A base page addressed with an extension token."""

    def __init__(self, base, token):
        self.base = base
        self.extension = token
        self.number = f"{base.number}#{token}"
        self.defined_in = getattr(base, "defined_in", type(base).__module__)
        self.title = base.title
        self.aliases = ()
        self.back_page = base.extension_back_page
        self.extension_back_page = base.extension_back_page
        self.requires = base.requires
        self.form = base.form
        self.transient = base.transient
        self.tick_interval = base.tick_interval
        self.no_screensaver = base.no_screensaver
        self.scroll = base.scroll
        self.paint = base.paint
        self.on_form = base.on_form
        self.header = base.header
        self.announce = base.announce
        self.announce_channel = base.announce_channel
        self.regions = base.regions
        self.default_focus = base.default_focus
        self.meta = {
            **(getattr(base, "meta", {}) or {}),
            "extension": token,
        }

    def render(self, ctx):
        return self.base.render(ctx)

    def on_submit(self, ctx, line):
        return self.base.on_submit(ctx, line)

    def on_key(self, ctx, key):
        return self.base.on_key(ctx, key)

    def on_tick(self, ctx):
        return self.base.on_tick(ctx)

    def on_back(self, ctx):
        return self.base.on_back(ctx)


def page(number, *, title="", aliases=(), on_submit=None, on_key=None,
         on_tick=None, tick_interval=None, form=False, on_form=None,
         on_back=None, transient=False, back_page=None, extension_back_page=None,
         screensaver=None, no_screensaver=False, scroll=False, paint=None,
         requires=(), extensions=False, header=None, announce=None,
         announce_channel=None, meta=None, regions=(), default_focus=None):
    def decorator(fn):
        return FunctionPage(
            number,
            fn,
            title=title,
            aliases=aliases,
            on_submit=on_submit,
            on_key=on_key,
            on_tick=on_tick,
            tick_interval=tick_interval,
            form=form,
            on_form=on_form,
            on_back=on_back,
            transient=transient,
            back_page=back_page,
            extension_back_page=extension_back_page,
            screensaver=screensaver,
            no_screensaver=no_screensaver,
            scroll=scroll,
            paint=paint,
            requires=requires,
            extensions=extensions,
            header=header,
            announce=announce,
            announce_channel=announce_channel,
            meta=meta,
            regions=regions,
            default_focus=default_focus,
        )
    return decorator


def split_extension(key):
    """Return ``(base, token)`` for a valid extension route, else ``None``."""
    key = key.strip()
    for separator in EXTENSION_SEPARATORS[1:]:
        key = key.replace(separator, EXTENSION_SEPARATORS[0])
    if key.count(EXTENSION_SEPARATORS[0]) != 1:
        return None
    base, token = key.split(EXTENSION_SEPARATORS[0])
    if not base or not token or len(token) > MAX_EXTENSION_LENGTH:
        return None
    if not token.isascii() or not token.isalnum():
        return None
    return base, token.upper()


@dataclass(frozen=True)
class KeyOverride:
    key: str
    kind: str
    old_page: Page
    new_page: Page
    old_source: object = None
    new_source: object = None


class Registry:
    def __init__(self):
        self._pages = []
        self._by_key = {}
        self._sources = {}
        self._overrides = []
        self._announcers = {}

    def add(self, page: Page, *, source=None, on_conflict="error"):
        if on_conflict not in ("error", "override"):
            raise ValueError(
                "on_conflict must be 'error' or 'override'"
            )
        if any(existing is page for existing in self._pages):
            return page
        validate_regions(
            getattr(page, "regions", ()),
            default_focus=getattr(page, "default_focus", None),
            form=getattr(page, "form", False),
            scroll=getattr(page, "scroll", False),
        )
        keys = (page.number, *page.aliases)
        for key in keys:
            if any(
                separator in key for separator in EXTENSION_SEPARATORS
            ):
                raise ValueError(
                    f"page key {key!r} must not contain an extension "
                    "separator"
                )
        self._check_announcer_conflict(page, source, on_conflict)

        if on_conflict == "error":
            for key in keys:
                existing = self._by_key.get(key)
                if existing is not None:
                    raise ValueError(
                        f"page key {key!r} already registered by "
                        f"{existing.title!r}"
                    )
        else:
            for key in keys:
                existing = self._by_key.get(key)
                if existing is None:
                    continue
                if self._sources.get(id(existing)) == source:
                    raise ValueError(
                        f"page key {key!r} already registered by "
                        f"{existing.title!r} in the same package "
                        f"{source!r}"
                    )

            overridden = []
            for key in keys:
                existing = self._by_key.get(key)
                if (
                    existing is not None
                    and existing.number == key
                    and not any(item is existing for item in overridden)
                ):
                    overridden.append(existing)
            for existing in overridden:
                old_source = self._sources.get(id(existing))
                self._remove_page(existing)
                self._overrides.append(
                    KeyOverride(
                        key=existing.number,
                        kind="page",
                        old_page=existing,
                        new_page=page,
                        old_source=old_source,
                        new_source=source,
                    )
                )

            for key in keys:
                existing = self._by_key.get(key)
                if existing is None or existing is page:
                    continue
                self._overrides.append(
                    KeyOverride(
                        key=key,
                        kind="alias",
                        old_page=existing,
                        new_page=page,
                        old_source=self._sources.get(id(existing)),
                        new_source=source,
                    )
                )
                self._by_key[key] = page

        self._pages.append(page)
        for key in keys:
            self._by_key[key] = page
        self._sources[id(page)] = source
        self._register_announcer(page, source, on_conflict)
        return page

    def _check_announcer_conflict(self, page, source, on_conflict):
        channel = announcement_channel(page)
        if channel is None:
            return
        existing = self._announcers.get(channel)
        if existing is None:
            return
        old_page, _, old_source = existing
        if old_source == source:
            raise ValueError(
                f"announcement channel {channel!r} already registered by "
                f"page {old_page.number!r} in the same package {source!r}"
            )
        if on_conflict == "error":
            raise ValueError(
                f"announcement channel {channel!r} already registered by "
                f"page {old_page.number!r}"
            )

    def _register_announcer(self, page, source, on_conflict):
        channel = announcement_channel(page)
        if channel is None:
            return
        existing = self._announcers.get(channel)
        if existing is not None:
            old_page, _, old_source = existing
            self._overrides.append(
                KeyOverride(
                    key=channel,
                    kind="announcement",
                    old_page=old_page,
                    new_page=page,
                    old_source=old_source,
                    new_source=source,
                )
            )
        self._announcers[channel] = (page, page.announce, source)

    def _remove_page(self, page):
        self._pages = [
            existing for existing in self._pages if existing is not page
        ]
        for key in (page.number, *page.aliases):
            if self._by_key.get(key) is page:
                del self._by_key[key]
        self._sources.pop(id(page), None)
        for channel, (owner, _, _) in tuple(self._announcers.items()):
            if owner is page:
                del self._announcers[channel]

    def announcers(self):
        """Return resolved ``(channel, page, provider)`` sources."""
        return tuple(
            (
                channel,
                self._announcers[channel][0],
                self._announcers[channel][1],
            )
            for channel in sorted(self._announcers)
        )

    @property
    def overrides(self):
        return tuple(self._overrides)

    def aliases_for(self, page):
        owned = {
            key
            for key, owner in self._by_key.items()
            if owner is page and key != page.number
        }
        declared = tuple(alias for alias in page.aliases if alias in owned)
        return declared + tuple(sorted(owned - set(declared)))

    def get(self, key):
        key = str(key).strip()
        page = self._by_key.get(key)
        if page is not None:
            return page
        route = split_extension(key)
        if route is None:
            return None
        base_key, token = route
        base = self._by_key.get(base_key)
        if base is None or not base.extensions:
            return None
        return ExtensionPage(base, token)

    def resolve(self, key):
        page = self.get(key)
        if page is None:
            raise KeyError(key)
        return page

    def missing_requirements(self, services):
        missing = {}
        for page in self._pages:
            required = list(page.requires)
            header = getattr(page, "header", None)
            if header is not None and header is not False:
                required.extend(header_requires(header))
            for key in required:
                if key not in services:
                    numbers = missing.setdefault(key, [])
                    if page.number not in numbers:
                        numbers.append(page.number)
        return {
            key: tuple(numbers) for key, numbers in missing.items()
        }

    def screensaver_groups(self):
        groups = {}
        for page in self._pages:
            name = page.screensaver
            if isinstance(name, str) and name:
                groups.setdefault(name, []).append(page)
        return {
            name: tuple(sorted(groups[name], key=lambda page: page.number))
            for name in sorted(
                groups,
                key=lambda name: min(page.number for page in groups[name]),
            )
        }

    def screensaver_pages(self, name):
        if name == "all":
            return tuple(
                page
                for pages in self.screensaver_groups().values()
                for page in pages
            )
        return self.screensaver_groups().get(name)

    def all(self):
        return tuple(self._pages)

    def discover(self, package_name, *, source=None, on_conflict="error"):
        if source is None:
            source = package_name
        package = importlib.import_module(package_name)
        modules = sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name)
        for module_info in modules:
            if module_info.ispkg:
                self.discover(
                    f"{package_name}.{module_info.name}",
                    source=source,
                    on_conflict=on_conflict,
                )
                continue
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            for value in vars(module).values():
                if isinstance(value, Page):
                    owner = getattr(value, "defined_in", None)
                    if owner is None:
                        owner = type(value).__module__
                    if owner != module.__name__:
                        continue
                    self.add(
                        value,
                        source=source,
                        on_conflict=on_conflict,
                    )
        return self
