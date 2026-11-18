"""Declarative fixed-width columns for ``minitel.Screen``."""

from dataclasses import dataclass, field

from minitel import codec

ALIGNMENTS = ("left", "right", "center")


@dataclass(frozen=True)
class Column:
    """One fixed-width column.

    ``attrs`` are merged into the row attributes; ``fg`` is a shorthand for a
    column colour. Widths count screen cells, not characters in the value.
    """

    title: str
    width: int
    align: str = "left"
    fg: int | None = None
    attrs: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.width < 1:
            raise ValueError("column width must be at least 1")
        if self.align not in ALIGNMENTS:
            raise ValueError(f"column align must be one of {ALIGNMENTS}")
        if self.fg is not None and not isinstance(self.fg, int):
            raise TypeError("column fg must be an int or None")
        if not isinstance(self.attrs, dict):
            raise TypeError("column attrs must be a dict")

    def format(self, value, *, trim=False):
        text = "" if value is None else str(value)
        if len(text) > self.width:
            text = (
                text[-self.width:]
                if self.align == "right"
                else text[:self.width]
            )
        if self.align == "right":
            text = text.rjust(self.width)
        elif self.align == "center":
            text = text.center(self.width)
        else:
            text = text.ljust(self.width)
        return text.rstrip() if trim else text

    def merged_attrs(self, attrs=None):
        merged = dict(attrs or {})
        merged.update(self.attrs)
        if self.fg is not None:
            merged["fg"] = self.fg
        return merged


@dataclass(frozen=True, init=False)
class Table:
    """A header plus rows of fixed-width columns.

    The last column is not padded with trailing spaces, so a table can end at
    its content instead of writing to the screen edge.
    """

    columns: tuple[Column, ...]
    gap: int = 1
    trim_last: bool = True

    def __init__(self, *columns, gap=1, trim_last=True):
        object.__setattr__(self, "columns", tuple(columns))
        object.__setattr__(self, "gap", gap)
        object.__setattr__(self, "trim_last", trim_last)
        self.__post_init__()

    def __post_init__(self):
        if not self.columns:
            raise ValueError("a table needs at least one column")
        if not all(isinstance(column, Column) for column in self.columns):
            raise TypeError("table columns must be Column values")
        if self.gap < 0:
            raise ValueError("table gap must be non-negative")
        if not isinstance(self.trim_last, bool):
            raise TypeError("table trim_last must be a bool")
        if self.width > codec.COLS:
            raise ValueError(
                f"table width {self.width} exceeds {codec.COLS} columns"
            )

    @property
    def width(self):
        return (
            sum(column.width for column in self.columns)
            + self.gap * (len(self.columns) - 1)
        )

    def header(self, screen, row, col=0, *, attrs=None):
        self._draw(screen, row, col, [column.title for column in self.columns],
                   attrs=attrs)

    def row(self, screen, row, values, col=0, *, attrs=None):
        self._draw(screen, row, col, values, attrs=attrs)

    def format(self, values):
        values = tuple(values)
        if len(values) != len(self.columns):
            raise ValueError(
                f"table needs {len(self.columns)} values, got {len(values)}"
            )
        parts = []
        last = len(self.columns) - 1
        for index, (column, value) in enumerate(zip(self.columns, values)):
            parts.append(column.format(
                value, trim=self.trim_last and index == last
            ))
        return (" " * self.gap).join(parts)

    def _draw(self, screen, row, col, values, *, attrs):
        values = tuple(values)
        if len(values) != len(self.columns):
            raise ValueError(
                f"table needs {len(self.columns)} values, got {len(values)}"
            )
        cursor = col
        last = len(self.columns) - 1
        for index, (column, value) in enumerate(zip(self.columns, values)):
            text = column.format(
                value, trim=self.trim_last and index == last
            )
            if text:
                screen.text(
                    row, cursor, text,
                    **column.merged_attrs(attrs),
                )
            cursor += column.width + self.gap
