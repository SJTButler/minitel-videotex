"""Selected match stops for a viewport.

A stop is a matching link target rendered in the viewport. The session owns the
selected stop and the viewport offset; the page declares the stops and draws the
selected target.
"""

from dataclasses import dataclass, replace

from .viewport import Viewport


@dataclass(frozen=True)
class Stop:
    first_line: int
    line: int
    link: int

    def __post_init__(self):
        if self.first_line < 0 or self.line < 0:
            raise ValueError("stop line must not be negative")
        if self.link < 0:
            raise ValueError("stop link must not be negative")


@dataclass(frozen=True)
class Stops:
    stops: tuple[Stop, ...]
    selected: int | None = None
    start_next: int = 0
    start_prev: int = 0
    wrap: bool = True

    def __post_init__(self):
        object.__setattr__(self, "stops", tuple(self.stops))

    @property
    def selected_stop(self):
        if self.selected is None or not self.stops:
            return None
        return self.stops[self.selected]

    @property
    def identity(self):
        return tuple((stop.first_line, stop.link) for stop in self.stops)

    def clamp(self):
        count = len(self.stops)
        if not count:
            return replace(self, selected=None, start_next=0, start_prev=0)
        selected = self.selected
        if selected is not None and not 0 <= selected < count:
            selected = min(max(selected, 0), count - 1)
        return replace(
            self,
            selected=selected,
            start_next=min(max(self.start_next, 0), count - 1),
            start_prev=min(max(self.start_prev, 0), count - 1),
        )

    def next(self):
        view = self.clamp()
        if not view.stops:
            return view
        if view.selected is None:
            return replace(view, selected=view.start_next)
        if view.selected + 1 < len(view.stops):
            return replace(view, selected=view.selected + 1)
        return replace(view, selected=0 if view.wrap else view.selected)

    def prev(self):
        view = self.clamp()
        if not view.stops:
            return view
        if view.selected is None:
            return replace(view, selected=view.start_prev)
        if view.selected > 0:
            return replace(view, selected=view.selected - 1)
        last = len(view.stops) - 1
        return replace(view, selected=last if view.wrap else view.selected)


def reveal_offset(viewport, line, *, context=1):
    """Return an offset that reveals ``line`` in ``viewport``."""
    if viewport is None:
        return 0
    view = viewport.clamp()
    if not view.total:
        return 0
    line = min(max(int(line), 0), view.total - 1)
    if line < view.offset:
        return max(0, line - context)
    if line >= view.offset + view.height:
        return min(view.max_offset, line - view.height + 1 + context)
    return view.offset


def reveal_viewport(viewport, line, *, context=1):
    """Return a non-following viewport positioned to reveal ``line``."""
    if viewport is None:
        return None
    view = viewport.clamp()
    offset = reveal_offset(view, line, context=context)
    return Viewport(
        view.total, view.height, offset, False, view.step
    ).clamp()
