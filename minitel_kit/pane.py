"""Clipped rectangular panes for ``minitel.Screen``."""

from dataclasses import dataclass

from minitel import codec


@dataclass(frozen=True)
class Rect:
    """A clipped drawing rectangle.

    Rows and columns passed to ``text``, ``fill``, ``rule``, and ``field`` are
    relative to the rectangle's top-left corner. ``screen`` is always the
    absolute ``minitel.Screen``.
    """

    top: int
    left: int
    height: int
    width: int

    def __post_init__(self):
        for name, value in (
            ("top", self.top), ("left", self.left),
            ("height", self.height), ("width", self.width),
        ):
            if not isinstance(value, int):
                raise TypeError(f"rect {name} must be an int")
        if self.height < 1 or self.width < 1:
            raise ValueError("rect height and width must be positive")
        if self.top < 0 or self.left < 0:
            raise ValueError("rect top and left must be non-negative")
        if self.top + self.height > codec.ROWS:
            raise ValueError("rect extends below the screen")
        if self.left + self.width > codec.COLS:
            raise ValueError("rect extends past the right edge")

    @property
    def bottom(self):
        return self.top + self.height

    @property
    def right(self):
        return self.left + self.width

    def contains(self, row, col):
        return 0 <= row < self.height and 0 <= col < self.width

    def text(self, screen, row, col, value, **attrs):
        self._check(row, col)
        available = self.width - col
        screen.text(
            self.top + row,
            self.left + col,
            str(value)[:available],
            **attrs,
        )

    def fill(self, screen, row, col, width, ch=" ", **attrs):
        self._check(row, col)
        if width < 0:
            raise ValueError("fill width must be non-negative")
        screen.fill(
            self.top + row,
            self.left + col,
            min(width, self.width - col),
            ch,
            **attrs,
        )

    def rule(self, screen, row, col=0, width=None, ch="=", **attrs):
        self._check(row, col)
        if width is None:
            width = self.width - col
        self.fill(screen, row, col, width, ch, **attrs)

    def field(self, screen, row, col, width, **attrs):
        self._check(row, col)
        screen.field(
            self.top + row,
            self.left + col,
            min(width, self.width - col),
            **attrs,
        )

    def sub(self, top, left, height, width):
        if (
            top < 0 or left < 0 or height < 1 or width < 1
            or top + height > self.height
            or left + width > self.width
        ):
            raise ValueError("sub-rectangle must fit inside its parent")
        return Rect(self.top + top, self.left + left, height, width)

    def _check(self, row, col):
        if not self.contains(row, col):
            raise ValueError(
                f"pane position ({row}, {col}) outside "
                f"{self.height}x{self.width} rect"
            )
