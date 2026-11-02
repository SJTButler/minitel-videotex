"""25x40 screen model."""

from dataclasses import dataclass

from ..protocol import codec


@dataclass
class Cell:
    ch: str = " "
    fg: int = codec.WHITE
    bg: int = codec.BLACK
    inverse: bool = False
    flash: bool = False
    underline: bool = False
    size: int = codec.NORMAL


SIZES = (
    codec.NORMAL,
    codec.DOUBLE_HEIGHT,
    codec.DOUBLE_WIDTH,
    codec.DOUBLE_SIZE,
)


def _check_size(size):
    if size not in SIZES:
        raise ValueError(f"unknown size {size!r}")


def _span(width, height, size):
    if size in (codec.DOUBLE_WIDTH, codec.DOUBLE_SIZE):
        width *= 2
    if size in (codec.DOUBLE_HEIGHT, codec.DOUBLE_SIZE):
        height *= 2
    return width, height


def _check_cell(ch):
    if not isinstance(ch, str) or len(ch) != 1:
        raise ValueError(f"cell value must be one character, got {ch!r}")


def _check_placement(row, col, width, height, size, what):
    _check_size(size)
    width, height = _span(width, height, size)
    if not 0 <= row < codec.ROWS:
        raise ValueError(f"row {row} outside 0..{codec.ROWS - 1}")
    if not 0 <= col < codec.COLS:
        raise ValueError(f"column {col} outside 0..{codec.COLS - 1}")
    if col + width > codec.COLS:
        raise ValueError(
            f"{what} at row {row}, column {col} overflows the row "
            f"({width} cells, size {size})"
        )
    if row + height > codec.ROWS:
        raise ValueError(
            f"{what} at row {row} overflows the screen "
            f"({height} rows, size {size})"
        )


class Screen:
    def __init__(self):
        self.rows = [[Cell() for _ in range(codec.COLS)] for _ in range(codec.ROWS)]
        self.cursor_row = 1
        self.cursor_col = 0
        self.cursor_visible = True

    def clear(self):
        for row in self.rows:
            for i in range(codec.COLS):
                row[i] = Cell()
        self.cursor_row = 1
        self.cursor_col = 0
        self.cursor_visible = True

    def put(self, row, col, ch, **attrs):
        _check_cell(ch)
        size = attrs.get("size", codec.NORMAL)
        _check_placement(row, col, 1, 1, size, "cell")
        self.rows[row][col] = Cell(ch=ch, **attrs)

    def text(self, row, col, value, **attrs):
        if not isinstance(value, str):
            raise TypeError(f"text value must be a string, got {type(value)!r}")
        size = attrs.get("size", codec.NORMAL)
        _check_placement(row, col, len(value), 1, size, "text")
        for i, ch in enumerate(value):
            self.rows[row][col + i] = Cell(ch=ch, **attrs)

    def fill(self, row, col, width, ch=" ", **attrs):
        _check_cell(ch)
        if width < 0:
            raise ValueError(f"fill width must be non-negative, got {width}")
        size = attrs.get("size", codec.NORMAL)
        _check_placement(row, col, width, 1, size, "fill")
        for i in range(width):
            self.rows[row][col + i] = Cell(ch=ch, **attrs)

    def rule(self, row, col, width, ch="=", **attrs):
        self.fill(row, col, width, ch, **attrs)

    def field(self, row, col, width, **attrs):
        attrs.setdefault("inverse", True)
        self.fill(row, col, width, " ", **attrs)
        self.cursor_row = row
        self.cursor_col = col
        self.cursor_visible = True

    def set_cursor(self, row, col, visible=True):
        if not 0 <= row < codec.ROWS:
            raise ValueError(f"row {row} outside 0..{codec.ROWS - 1}")
        if not 0 <= col < codec.COLS:
            raise ValueError(f"column {col} outside 0..{codec.COLS - 1}")
        self.cursor_row = row
        self.cursor_col = col
        self.cursor_visible = visible

    def to_text(self):
        return "\n".join("".join(cell.ch for cell in row) for row in self.rows)
