"""Page API, page context, and registry."""

import importlib
import pkgutil
from dataclasses import dataclass

from .carousel import Carousel
from .paging import Pager
from .screen import Screen


@dataclass
class InputField:
    name: str
    row: int
    col: int
    width: int
    mask: str | None = None
    value: str = ""
    cursor: str = "visible"


CURSOR_MODES = ("visible", "hidden", "auto")


class PageContext:
    def __init__(self, session, page, registry):
        self.session = session
        self.page = page
        self.registry = registry
        self.fields = []
        self.values = session.values
        self.focus_name = None
        self.pager = None
        self.pager_carousel = None

    @property
    def line(self):
        return self.session.line

    @property
    def profile(self):
        return self.session.profile

    @property
    def last_key(self):
        return self.session.last_key

    @property
    def state(self):
        return self.session.state

    @property
    def services(self):
        return self.session.services

    def service(self, name, default=None):
        return self.services.get(name, default)

    @property
    def active_name(self):
        return self.session.requested_focus or self.session.active_name

    def add_field(self, name, row, col, width, *, mask=None, value="",
                  cursor="visible"):
        if cursor not in CURSOR_MODES:
            raise ValueError(f"cursor must be one of {CURSOR_MODES}")
        if any(field.name == name for field in self.fields):
            raise ValueError(f"duplicate field name {name!r}")
        field = InputField(
            name, row, col, width, mask=mask, value=value, cursor=cursor
        )
        self.fields.append(field)
        self.values.setdefault(name, value)
        return field

    def set_input(self, row, col, width, *, mask=None, value="",
                  cursor="visible"):
        return self.add_field(
            "input", row, col, width,
            mask=mask, value=value, cursor=cursor,
        )

    def set_pager(self, total, page_size, *, offset=None, carousel=None):
        if carousel is not None and not isinstance(carousel, Carousel):
            raise TypeError("carousel must be a Carousel or None")
        if offset is None:
            current = self.session.pager
            if current is not None:
                offset = current.offset
            else:
                stored = self.session.pagers.get(self.page.number)
                offset = stored.offset if stored is not None else 0
        self.pager = Pager(total, page_size, offset).clamp()
        self.pager_carousel = carousel
        return self.pager

    @property
    def screensaver(self):
        return self.session.screensaver

    @property
    def idle_elapsed(self):
        return self.session.idle_elapsed

    def set_screensaver(self, pages, *, after=120.0, hold=20.0, wrap=True):
        return self.session.set_screensaver(
            pages, after=after, hold=hold, wrap=wrap
        )

    def disable_screensaver(self):
        return self.session.disable_screensaver()

    def start_screensaver(self, index=0):
        return self.session.request_screensaver(index)

    def field(self, name):
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def focus(self, name):
        self.session.requested_focus = name

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
    screensaver = None
    no_screensaver = False
    tick_interval = None
    on_form = None

    def render(self, ctx: PageContext) -> Screen:
        raise NotImplementedError

    def on_submit(self, ctx: PageContext, line: str):
        return None

    def on_key(self, ctx: PageContext, key: str):
        return None

    def on_tick(self, ctx):
        return None

    def matches(self, key: str) -> bool:
        return key == self.number or key in self.aliases


class FunctionPage(Page):
    def __init__(self, number, render, *, title="", aliases=(), on_submit=None,
                 on_key=None, on_tick=None, tick_interval=None, form=False,
                 on_form=None, transient=False, back_page=None,
                 screensaver=None, no_screensaver=False, meta=None):
        if screensaver is not None and (
            not isinstance(screensaver, str) or not screensaver
        ):
            raise TypeError("screensaver must be a non-empty string or None")
        self.number = number
        self._render = render
        self.title = title
        self.aliases = tuple(aliases)
        self.back_page = back_page
        self.screensaver = screensaver or None
        self.no_screensaver = bool(no_screensaver)
        self._on_submit = on_submit
        self._on_key = on_key
        self._on_tick = on_tick
        self.tick_interval = tick_interval
        self.form = form
        self.on_form = on_form
        self.transient = transient
        self.meta = dict(meta or {})

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


def page(number, *, title="", aliases=(), on_submit=None, on_key=None,
         on_tick=None, tick_interval=None, form=False, on_form=None,
         transient=False, back_page=None, screensaver=None,
         no_screensaver=False, **meta):
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
            transient=transient,
            back_page=back_page,
            screensaver=screensaver,
            no_screensaver=no_screensaver,
            meta=meta,
        )
    return decorator


class Registry:
    def __init__(self):
        self._pages = []
        self._by_key = {}

    def add(self, page: Page):
        for key in (page.number, *page.aliases):
            existing = self._by_key.get(key)
            if existing is page:
                continue
            if existing is not None:
                raise ValueError(
                    f"page key {key!r} already registered by {existing.title!r}"
                )
        self._pages.append(page)
        for key in (page.number, *page.aliases):
            self._by_key[key] = page
        return page

    def get(self, key):
        return self._by_key.get(key.strip())

    def resolve(self, key):
        page = self.get(key)
        if page is None:
            raise KeyError(key)
        return page

    def screensaver_groups(self):
        groups = {}
        for page in self._pages:
            name = page.screensaver
            if isinstance(name, str) and name:
                groups.setdefault(name, []).append(page)
        return {
            name: tuple(groups[name])
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

    def discover(self, package_name):
        package = importlib.import_module(package_name)
        modules = sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name)
        for module_info in modules:
            if module_info.ispkg:
                self.discover(f"{package_name}.{module_info.name}")
                continue
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            for value in vars(module).values():
                if isinstance(value, Page):
                    self.add(value)
        return self
