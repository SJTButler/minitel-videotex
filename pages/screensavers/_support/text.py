"""Load the public-domain text used by the scrolling screensaver."""

from pathlib import Path

from minitel.protocol import codec
from minitel.text import sanitize, wrap


# Keep one column free. A scrolling row that ends in column 40 can trigger the
# terminal's overflow path on the bottom row and add an extra scroll.
WIDTH = codec.COLS - 1


def _load():
    path = Path(__file__).parent / "texts" / "shakespeare.txt"
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = sanitize(raw)
        if not line:
            lines.append("")
            continue
        lines.extend(wrap(line, WIDTH))
    return tuple(lines)


LINES = _load()
