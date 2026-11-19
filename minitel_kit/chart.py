"""Mosaic bar and line charts for ``minitel.Screen``."""

from dataclasses import dataclass

from .mosaic import MosaicCanvas


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_size(width, height):
    for name, value in (("width", width), ("height", height)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"chart {name} must be an int")
        if value < 1:
            raise ValueError(f"chart {name} must be positive")


def _check_range(minimum, maximum):
    for name, value in (("minimum", minimum), ("maximum", maximum)):
        if value is not None and not _is_number(value):
            raise TypeError(f"chart {name} must be a number or None")
    if (
        minimum is not None
        and maximum is not None
        and maximum <= minimum
    ):
        raise ValueError("chart maximum must be greater than minimum")


def _check_fg(fg):
    if fg is not None and (
        not isinstance(fg, int) or isinstance(fg, bool)
    ):
        raise TypeError("chart fg must be an int or None")


def _range(values, minimum, maximum):
    values = [value for value in values if value is not None]
    if not values:
        return None, None
    low = minimum if minimum is not None else min(values)
    high = maximum if maximum is not None else max(values)
    if high <= low:
        high = low + 1
    return low, high


@dataclass(frozen=True)
class Bars:
    """Vertical mosaic bars scaled into a fixed cell area."""

    width: int
    height: int
    minimum: float | None = None
    maximum: float | None = None
    gap: int = 0
    fg: int | None = None

    def __post_init__(self):
        _check_size(self.width, self.height)
        if not isinstance(self.gap, int) or isinstance(self.gap, bool):
            raise TypeError("chart gap must be an int")
        if self.gap < 0:
            raise ValueError("chart gap must be non-negative")
        _check_range(self.minimum, self.maximum)
        _check_fg(self.fg)

    def draw(self, screen, row, col, values, **attrs):
        values = tuple(values)
        if not values:
            return
        low, high = _range(values, self.minimum, self.maximum)
        if low is None:
            return
        bar_width = max(
            1, (self.width - self.gap * (len(values) - 1)) // len(values)
        )
        canvas = MosaicCanvas(self.width, self.height)
        pixel_height = canvas.pixel_height
        for index, value in enumerate(values):
            if value is None:
                continue
            start = index * (bar_width + self.gap)
            if start >= self.width:
                break
            end = min(start + bar_width, self.width)
            ratio = (value - low) / (high - low)
            ratio = min(1.0, max(0.0, ratio))
            pixels = round(ratio * pixel_height)
            for x in range(start * 2, end * 2):
                for y in range(pixel_height - pixels, pixel_height):
                    canvas.set(x, y)
        attrs = dict(attrs)
        if self.fg is not None:
            attrs.setdefault("fg", self.fg)
        canvas.draw(screen, row, col, **attrs)


@dataclass(frozen=True)
class Sparkline:
    """A mosaic line through values in a fixed cell area."""

    width: int
    height: int
    minimum: float | None = None
    maximum: float | None = None
    fg: int | None = None

    def __post_init__(self):
        _check_size(self.width, self.height)
        _check_range(self.minimum, self.maximum)
        _check_fg(self.fg)

    def draw(self, screen, row, col, values, **attrs):
        values = tuple(values)
        if not values:
            return
        low, high = _range(values, self.minimum, self.maximum)
        if low is None:
            return
        canvas = MosaicCanvas(self.width, self.height)
        pixel_width = canvas.pixel_width
        pixel_height = canvas.pixel_height
        previous = None
        for index, value in enumerate(values):
            if value is None:
                previous = None
                continue
            if len(values) == 1:
                x = (pixel_width - 1) // 2
            else:
                x = round(index * (pixel_width - 1) / (len(values) - 1))
            ratio = (value - low) / (high - low)
            ratio = min(1.0, max(0.0, ratio))
            y = pixel_height - 1 - round(ratio * (pixel_height - 1))
            if previous is None:
                canvas.set(x, y)
            else:
                canvas.line(previous[0], previous[1], x, y)
            previous = (x, y)
        attrs = dict(attrs)
        if self.fg is not None:
            attrs.setdefault("fg", self.fg)
        canvas.draw(screen, row, col, **attrs)
