"""Page API, page context, and registry."""

import importlib
import pkgutil
from dataclasses import dataclass

from ..design.carousel import Carousel
from ..design.field import InputField
from ..design.pager import Pager
from ..render.screen import Screen


CURSOR_MODES = ("visible", "hidden", "auto")
LINE_FIELD = "input"
EXTENSION_SEPARATORS = ("#", "£")
MAX_EXTENSION_LENGTH = 6


class PageContext:
    def __init__(self, session, page, registry):
        self._session = session
        self.page = page
        self.registry = registry
        self.fields = []
        self.values = session.values
        self.focus_name = None
        self.pager = None
        self.pager_carousel = None

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

    @property
    def active_name(self):
        return self._session.requested_focus or self._session.active_name

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

    @property
    def input_value(self):
        return self.values.get(LINE_FIELD, "")

    def clear_input(self):
        self.values[LINE_FIELD] = ""

    def set_input(self, row, col, width, *, mask=None, value="",
                  cursor="visible"):
        return self.add_field(
            LINE_FIELD, row, col, width,
            mask=mask, value=value, cursor=cursor,
        )

    def set_pager(self, total, page_size, *, offset=None, carousel=None):
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
    tick_interval = None
    on_form = None
    requires = ()
    extensions = False

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
                 extension_back_page=None, screensaver=None,
                 no_screensaver=False, scroll=False, requires=(),
                 extensions=False, meta=None):
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
        self.number = number
        self._render = render
        self.title = title
        self.aliases = tuple(aliases)
        self.requires = requires
        self.back_page = back_page
        self.extension_back_page = extension_back_page
        self.screensaver = screensaver or None
        self.no_screensaver = bool(no_screensaver)
        self.scroll = bool(scroll)
        self.extensions = bool(extensions)
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


class ExtensionPage(Page):
    """A base page addressed with an extension token."""

    def __init__(self, base, token):
        self.base = base
        self.extension = token
        self.number = f"{base.number}#{token}"
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
        self.on_form = base.on_form
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


def page(number, *, title="", aliases=(), on_submit=None, on_key=None,
         on_tick=None, tick_interval=None, form=False, on_form=None,
         transient=False, back_page=None, extension_back_page=None,
         screensaver=None, no_screensaver=False, scroll=False, requires=(),
         extensions=False, **meta):
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
            extension_back_page=extension_back_page,
            screensaver=screensaver,
            no_screensaver=no_screensaver,
            scroll=scroll,
            requires=requires,
            extensions=extensions,
            meta=meta,
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

    def add(self, page: Page, *, source=None, on_conflict="error"):
        if on_conflict not in ("error", "override"):
            raise ValueError(
                "on_conflict must be 'error' or 'override'"
            )
        if any(existing is page for existing in self._pages):
            return page
        keys = (page.number, *page.aliases)
        for key in keys:
            if any(
                separator in key for separator in EXTENSION_SEPARATORS
            ):
                raise ValueError(
                    f"page key {key!r} must not contain an extension "
                    "separator"
                )

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
        return page

    def _remove_page(self, page):
        self._pages = [
            existing for existing in self._pages if existing is not page
        ]
        for key in (page.number, *page.aliases):
            if self._by_key.get(key) is page:
                del self._by_key[key]
        self._sources.pop(id(page), None)

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
            for key in page.requires:
                if key not in services:
                    missing.setdefault(key, []).append(page.number)
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
                    self.add(
                        value,
                        source=source,
                        on_conflict=on_conflict,
                    )
        return self
