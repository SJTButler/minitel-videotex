"""Screensaver configuration: pages, idle delay, and hold time."""

from dataclasses import dataclass

from .pages import Page


@dataclass(frozen=True)
class Screensaver:
    pages: tuple[Page, ...]
    after: float | None = 120.0
    hold: float = 20.0

    @classmethod
    def from_spec(cls, registry, spec, *, after=120.0, hold=20.0):
        if isinstance(spec, cls):
            return spec
        if isinstance(spec, (str, Page)):
            spec = (spec,)
        pages = []
        for item in spec:
            if isinstance(item, Page):
                page = item
            else:
                page = registry.get(str(item))
            if page is None:
                raise KeyError(f"unknown screensaver page {item!r}")
            pages.append(page)
        if not pages:
            raise ValueError("a screensaver needs at least one page")
        return cls(tuple(pages), after=after, hold=hold)
