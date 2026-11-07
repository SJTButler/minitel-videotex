"""Viewport arithmetic for a contiguous line buffer."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Viewport:
    total: int
    height: int
    offset: int = 0
    follow: bool = False
    step: int = 1

    def __post_init__(self):
        if self.height <= 0:
            raise ValueError("height must be positive")
        if self.total < 0:
            raise ValueError("total must not be negative")
        if self.step <= 0:
            raise ValueError("step must be positive")

    @property
    def max_offset(self):
        return max(0, self.total - self.height)

    @property
    def at_top(self):
        return self.clamp().offset == 0

    @property
    def at_bottom(self):
        view = self.clamp()
        return view.offset >= view.max_offset

    @property
    def line_number(self):
        if not self.total:
            return 0
        return min(self.clamp().offset + 1, self.total)

    def clamp(self):
        offset = min(max(0, self.offset), self.max_offset)
        return Viewport(
            self.total, self.height, offset, self.follow, self.step
        )

    def window(self, lines):
        view = self.clamp()
        return tuple(lines[view.offset:view.offset + view.height])

    def line_down(self):
        view = self.clamp()
        offset = min(view.offset + 1, view.max_offset)
        follow = offset >= view.max_offset
        return Viewport(
            view.total, view.height, offset, follow, view.step
        )

    def line_up(self):
        view = self.clamp()
        offset = max(view.offset - 1, 0)
        follow = view.follow if offset == view.offset else False
        return Viewport(
            view.total, view.height, offset, follow, view.step
        )

    def step_down(self):
        view = self.clamp()
        offset = min(view.offset + view.step, view.max_offset)
        follow = offset >= view.max_offset
        return Viewport(
            view.total, view.height, offset, follow, view.step
        )

    def step_up(self):
        view = self.clamp()
        offset = max(view.offset - view.step, 0)
        follow = view.follow if offset == view.offset else False
        return Viewport(
            view.total, view.height, offset, follow, view.step
        )

    def page_down(self, *, overlap=0):
        view = self.clamp()
        step = max(1, view.height - overlap)
        offset = min(view.offset + step, view.max_offset)
        follow = offset >= view.max_offset
        return Viewport(
            view.total, view.height, offset, follow, view.step
        )

    def page_up(self, *, overlap=0):
        view = self.clamp()
        step = max(1, view.height - overlap)
        offset = max(view.offset - step, 0)
        follow = view.follow if offset == view.offset else False
        return Viewport(
            view.total, view.height, offset, follow, view.step
        )

    def tail(self):
        return Viewport(
            self.total, self.height, self.max_offset, True, self.step
        )

    def with_total(self, total):
        view = Viewport(
            total, self.height, self.offset, self.follow, self.step
        )
        return view.tail() if view.follow else view.clamp()
