"""Timed advance policy for a page sequence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Carousel:
    hold: float = 30.0
    wrap: bool = True
    pages: tuple[int, ...] | None = None

    def __post_init__(self):
        if self.hold < 0:
            raise ValueError("hold must not be negative")
        if self.pages is not None:
            pages = tuple(self.pages)
            if any(
                isinstance(index, bool)
                or not isinstance(index, int)
                or index < 0
                for index in pages
            ):
                raise TypeError("carousel pages must be non-negative integers")
            object.__setattr__(self, "pages", pages)

    @property
    def active(self):
        return self.hold > 0

    def allowed(self, page_count):
        if self.pages is None:
            return tuple(range(max(0, page_count)))
        return tuple(
            index for index in self.pages if 0 <= index < page_count
        )
