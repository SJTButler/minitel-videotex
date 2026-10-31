"""25x40 screen model."""

from dataclasses import dataclass

from . import codec


@dataclass
class Cell:
    ch: str = " "
    fg: int = codec.WHITE
    bg: int = codec.BLACK
    inverse: bool = False
    flash: bool = False
    underline: bool = False
    size: int = codec.NORMAL


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
        if not 0 <= row < codec.ROWS:
            raise ValueError(f"row {row} outside 0..{codec.ROWS - 1}")
        if not 0 <= col < codec.COLS:
            raise ValueError(f"column {col} outside 0..{codec.COLS - 1}")
        self.rows[row][col] = Cell(ch=ch, **attrs)

    def text(self, row, col, value, **attrs):
        if not 0 <= row < codec.ROWS:
            raise ValueError(f"row {row} outside 0..{codec.ROWS - 1}")
        if not 0 <= col < codec.COLS:
            raise ValueError(f"column {col} outside 0..{codec.COLS - 1}")
        if col + len(value) > codec.COLS:
            raise ValueError("text overflows the row")
        for i, ch in enumerate(value):
            self.rows[row][col + i] = Cell(ch=ch, **attrs)

    def fill(self, row, col, width, ch=" ", **attrs):
        if not 0 <= row < codec.ROWS:
            raise ValueError(f"row {row} outside 0..{codec.ROWS - 1}")
        if width < 0 or col < 0 or col + width > codec.COLS:
            raise ValueError("fill outside the row")
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
