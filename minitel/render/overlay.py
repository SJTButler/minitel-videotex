"""Small screen composition helpers used by session chrome."""

from ..protocol import codec
from .screen import Cell, Screen


def compose_row(screen, row, cells):
    """Return a clone of ``screen`` with ``row`` replaced by ``cells``."""
    if not isinstance(screen, Screen):
        raise TypeError("screen must be a Screen")
    if not 0 <= row < codec.ROWS:
        raise ValueError(f"row {row} outside 0..{codec.ROWS - 1}")
    cells = tuple(cells)
    if len(cells) != codec.COLS:
        raise ValueError(
            f"row {row} must contain {codec.COLS} cells, got {len(cells)}"
        )
    composed = screen.clone()
    composed.rows[row] = [Cell(**vars(cell)) for cell in cells]
    return composed
