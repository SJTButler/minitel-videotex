"""Screensaver configuration: pages, idle delay, and carousel timing."""

from dataclasses import dataclass, field

from ..design.carousel import Carousel
from ..design.pager import Pager
from ..pagemodel.model import Page


@dataclass(frozen=True)
class Screensaver:
    pages: tuple[Page, ...]
    after: float | None = 120.0
    carousel: Carousel = field(default_factory=Carousel)

    def __post_init__(self):
        if not self.pages:
            raise ValueError("a screensaver needs at least one page")

    @property
    def hold(self):
        return self.carousel.hold

    @property
    def wrap(self):
        return self.carousel.wrap

    def page(self, index=0):
        pager = Pager(len(self.pages), 1, index)
        return pager.window(self.pages)[0]

    @classmethod
    def from_spec(cls, registry, spec, *, after=120.0, hold=20.0, wrap=True):
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
        return cls(
            tuple(pages),
            after=after,
            carousel=Carousel(hold=hold, wrap=wrap),
        )
