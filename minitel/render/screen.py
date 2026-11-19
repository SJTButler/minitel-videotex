"""25x40 screen model."""

from dataclasses import dataclass

from ..protocol import codec

PAINT_MODES = ("full", "row", "cell")
DIFF_PAINTS = ("row", "cell")


def validate_paint(value, *, allow_full=True, what="paint"):
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{what} must be a string or None")
    if value not in PAINT_MODES:
        raise ValueError(f"{what} must be one of {PAINT_MODES}")
    if not allow_full and value == "full":
        raise ValueError(f"{what} cannot be 'full'")
    return value


def resolve_paint(declared, override, *, allow_full=True, what="paint"):
    if override is not None:
        return validate_paint(
            override, allow_full=allow_full, what=f"{what} override"
        )
    value = validate_paint(declared, allow_full=allow_full, what=what)
    return value or "row"


@dataclass
class Cell:
    ch: str = " "
    fg: int = codec.WHITE
    bg: int = codec.BLACK
    inverse: bool = False
    flash: bool = False
    underline: bool = False
    size: int = codec.NORMAL
    continuation: bool = False
    mosaic: int | None = None


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


def _cell_span(size):
    """Return (columns, rows) occupied by one character of ``size``."""
    return _span(1, 1, size)


def _check_cell(ch):
    if not isinstance(ch, str) or len(ch) != 1:
        raise ValueError(f"cell value must be one character, got {ch!r}")


def _check_text_attrs(attrs, what):
    if "mosaic" in attrs:
        raise TypeError(
            f"{what} writes text cells; use Screen.put_mosaic for a G1 cell"
        )


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
        self.paint_order = "down"
        self.force_full = False
        self.paint = None

    def clear(self):
        """Clear cells and reset the cursor, not the frame presentation hints.

        ``paint``, ``paint_order``, and ``force_full`` describe the next frame,
        so they survive a content clear. Construct a new ``Screen`` or reset
        those attributes explicitly when a fresh presentation is wanted.
        """
        for row in self.rows:
            for i in range(codec.COLS):
                row[i] = Cell()
        self.cursor_row = 1
        self.cursor_col = 0
        self.cursor_visible = True

    def clone(self):
        clone = Screen()
        clone.rows = [
            [Cell(**vars(cell)) for cell in row]
            for row in self.rows
        ]
        clone.cursor_row = self.cursor_row
        clone.cursor_col = self.cursor_col
        clone.cursor_visible = self.cursor_visible
        clone.paint_order = self.paint_order
        clone.force_full = self.force_full
        clone.paint = self.paint
        return clone

    def put(self, row, col, ch, **attrs):
        _check_cell(ch)
        _check_text_attrs(attrs, "put")
        size = attrs.get("size", codec.NORMAL)
        _check_placement(row, col, 1, 1, size, "cell")
        self._check_free(row, col, 1, 1, size, "cell")
        self._place(row, col, ch, attrs, size)

    def put_mosaic(self, row, col, pattern, **attrs):
        """Place one 2x3 G1 block cell.

        ``pattern`` is a 0..63 block bitmap. The cell may use colour, inverse,
        and flash; double size and underline are not usable in G1.
        """
        if not isinstance(pattern, int) or isinstance(pattern, bool):
            raise TypeError("mosaic pattern must be an int")
        if not 0 <= pattern <= 63:
            raise ValueError("mosaic pattern must be 0..63")
        if "mosaic" in attrs:
            raise TypeError("put_mosaic takes the pattern directly")
        if "ch" in attrs:
            raise TypeError("put_mosaic takes the pattern, not a character")
        if attrs.get("continuation"):
            raise TypeError("mosaic cells cannot be continuation cells")
        size = attrs.get("size", codec.NORMAL)
        if size != codec.NORMAL:
            raise ValueError("mosaic cells cannot use double size")
        if attrs.get("underline"):
            raise ValueError("mosaic cells cannot use underline")
        _check_placement(row, col, 1, 1, size, "mosaic cell")
        self._check_free(row, col, 1, 1, size, "mosaic cell")
        self.rows[row][col] = Cell(ch=" ", mosaic=pattern, **attrs)

    def text(self, row, col, value, **attrs):
        if not isinstance(value, str):
            raise TypeError(f"text value must be a string, got {type(value)!r}")
        _check_text_attrs(attrs, "text")
        size = attrs.get("size", codec.NORMAL)
        _check_placement(row, col, len(value), 1, size, "text")
        self._check_free(row, col, len(value), 1, size, "text")
        columns, _rows = _cell_span(size)
        for i, ch in enumerate(value):
            self._place(row, col + i * columns, ch, attrs, size)

    def fill(self, row, col, width, ch=" ", **attrs):
        _check_cell(ch)
        _check_text_attrs(attrs, "fill")
        if width < 0:
            raise ValueError(f"fill width must be non-negative, got {width}")
        size = attrs.get("size", codec.NORMAL)
        _check_placement(row, col, width, 1, size, "fill")
        self._check_free(row, col, width, 1, size, "fill")
        columns, _rows = _cell_span(size)
        for i in range(width):
            self._place(row, col + i * columns, ch, attrs, size)

    def _check_free(self, row, col, width, height, size, what):
        columns, rows = _span(width, height, size)
        for r in range(row, row + rows):
            if self._row_reserved(r):
                raise ValueError(
                    f"{what} targets row {r}, reserved by double-height text "
                    "above"
                )
        for r in range(row, row + rows):
            for c in range(col, col + columns):
                cell = self.rows[r][c]
                if cell.continuation:
                    raise ValueError(
                        f"{what} overlaps a multi-cell run at row {r}, "
                        f"column {c}"
                    )
                if cell.size != codec.NORMAL:
                    raise ValueError(
                        f"{what} overlaps a size {cell.size} run at row {r}, "
                        f"column {c}"
                    )
                if r > row and cell.ch != " ":
                    raise ValueError(
                        f"{what} would overwrite text on row {r}"
                    )

    def _row_reserved(self, row):
        if row <= 0:
            return False
        return any(
            not cell.continuation
            and cell.size in (codec.DOUBLE_HEIGHT, codec.DOUBLE_SIZE)
            for cell in self.rows[row - 1]
        )

    def _place(self, row, col, ch, attrs, size):
        columns, rows = _cell_span(size)
        self.rows[row][col] = Cell(ch=ch, **attrs)
        for r in range(row, row + rows):
            for c in range(col, col + columns):
                if r == row and c == col:
                    continue
                self.rows[r][c] = Cell(
                    ch=" ", continuation=True, **attrs
                )

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
        return "\n".join(
            "".join(
                codec.mosaic_glyph(cell.mosaic)
                if cell.mosaic is not None
                else cell.ch
                for cell in row if not cell.continuation
            )
            for row in self.rows
        )
