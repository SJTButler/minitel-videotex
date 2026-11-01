"""Timed advance policy for a page sequence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Carousel:
    hold: float = 30.0
    wrap: bool = True

    def __post_init__(self):
        if self.hold < 0:
            raise ValueError("hold must not be negative")

    @property
    def active(self):
        return self.hold > 0
