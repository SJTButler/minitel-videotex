"""Videotex byte encoders and Minitel input parser."""

from dataclasses import dataclass

BEL = 0x07
BS = 0x08
LF = 0x0A
VT = 0x0B
FF = 0x0C
CR = 0x0D
SO = 0x0E
SI = 0x0F
CON = 0x11
REP = 0x12
SEP = 0x13
COF = 0x14
CAN = 0x18
SS2 = 0x19
ESC = 0x1B
RS = 0x1E
US = 0x1F

BLACK = 0
RED = 1
GREEN = 2
YELLOW = 3
BLUE = 4
MAGENTA = 5
CYAN = 6
WHITE = 7

NORMAL = 0
DOUBLE_HEIGHT = 1
DOUBLE_WIDTH = 2
DOUBLE_SIZE = 3

ECHO_ON = bytes([ESC, 0x3B, 0x61, 0x5A, 0x51])
ECHO_OFF = bytes([ESC, 0x3B, 0x60, 0x5A, 0x51])

SCROLL_ON = bytes([ESC, 0x3A, 0x69, 0x43])
SCROLL_OFF = bytes([ESC, 0x3A, 0x6A, 0x43])

ROWS = 25
COLS = 40

FUNCTION_KEYS = {
    0x41: "ENVOI",
    0x42: "RETOUR",
    0x43: "REPETITION",
    0x44: "GUIDE",
    0x45: "ANNULATION",
    0x46: "SOMMAIRE",
    0x47: "CORRECTION",
    0x48: "SUITE",
    0x49: "CONNEXION",
}

ARROWS = {
    0x41: "up",
    0x42: "down",
    0x43: "right",
    0x44: "left",
}

SPECIAL_KEYS = {
    b"\x1b[2J": "ctrl_enter",
    b"\x1b[H": "shift_enter",
    b"\x1b[M": "shift_up",
    b"\x1b[L": "shift_down",
    b"\x1b[P": "shift_left",
    b"\x1b[4h": "shift_right",
}

_ACCENT_SPECS = {
    "à": (0x41, "a"), "á": (0x42, "a"), "â": (0x43, "a"), "ä": (0x48, "a"),
    "è": (0x41, "e"), "é": (0x42, "e"), "ê": (0x43, "e"), "ë": (0x48, "e"),
    "ì": (0x41, "i"), "í": (0x42, "i"), "î": (0x43, "i"), "ï": (0x48, "i"),
    "ò": (0x41, "o"), "ó": (0x42, "o"), "ô": (0x43, "o"), "ö": (0x48, "o"),
    "ù": (0x41, "u"), "ú": (0x42, "u"), "û": (0x43, "u"), "ü": (0x48, "u"),
    "ÿ": (0x48, "y"), "ç": (0x4B, "c"),
}

_SPECIAL_SPECS = {
    "£": 0x23,
    "°": 0x30,
    "¼": 0x3C,
    "½": 0x3D,
    "¾": 0x3E,
    "←": 0x2C,
    "↑": 0x2D,
    "→": 0x2E,
    "↓": 0x2F,
    "Œ": 0x6A,
    "œ": 0x7A,
    "ß": 0x7B,
}

ACCENTS = {
    ch: bytes([SS2, code, ord(base)])
    for ch, (code, base) in _ACCENT_SPECS.items()
}
SPECIALS = {
    ch: bytes([SS2, code])
    for ch, code in _SPECIAL_SPECS.items()
}
ACCENTS_INV = {
    (code, base): ch
    for ch, (code, base) in _ACCENT_SPECS.items()
}
SPECIALS_INV = {
    code: ch
    for ch, code in _SPECIAL_SPECS.items()
}


def pos(row, col):
    """Cursor position. Rows 0-24, columns 0-39; column 0 is the first cell."""
    if not 0 <= row < ROWS:
        raise ValueError(f"row {row} outside 0..{ROWS - 1}")
    if not 0 <= col < COLS:
        raise ValueError(f"column {col} outside 0..{COLS - 1}")
    if row == 1 and col == 0:
        return bytes([RS])
    return bytes([US, 0x40 + row, 0x41 + col])


def home():
    return bytes([RS])


def clear():
    return bytes([FF])


def fg(colour):
    if not 0 <= colour <= 7:
        raise ValueError("colour must be 0..7")
    return bytes([ESC, 0x40 + colour])


def bg(colour):
    if not 0 <= colour <= 7:
        raise ValueError("colour must be 0..7")
    return bytes([ESC, 0x50 + colour])


def inverse(on=True):
    return bytes([ESC, 0x5D if on else 0x5C])


def flash(on=True):
    return bytes([ESC, 0x48 if on else 0x49])


def underline(on=True):
    return bytes([ESC, 0x5A if on else 0x59])


def size(mode=NORMAL):
    if mode not in (NORMAL, DOUBLE_HEIGHT, DOUBLE_WIDTH, DOUBLE_SIZE):
        raise ValueError("invalid size mode")
    return bytes([ESC, 0x4C + mode])


def text(value):
    out = bytearray()
    for ch in value:
        code = ord(ch)
        if 0x20 <= code <= 0x7E:
            out.append(code)
        elif ch in ACCENTS:
            out.extend(ACCENTS[ch])
        elif ch in SPECIALS:
            out.extend(SPECIALS[ch])
        else:
            raise ValueError(f"cannot encode {ch!r}")
    return bytes(out)


def repeat(ch, count):
    if count <= 0:
        return b""
    out = bytearray(text(ch))
    if count == 1:
        return bytes(out)
    remaining = count - 1
    while remaining > 63:
        out.extend([REP, 0x40 + 63])
        remaining -= 63
    if remaining:
        out.extend([REP, 0x40 + remaining])
    return bytes(out)


def mosaic(value):
    if not 0x20 <= value <= 0x7F:
        raise ValueError("mosaic byte must be 0x20..0x7F")
    return bytes([SO, value, SI])


def charset(mosaic=False):
    """Select G1 semi-graphics (``SO``) or G0 text (``SI``)."""
    return bytes([SO if mosaic else SI])


def g1_byte(pattern):
    """Encode a 0..63 2x3 block pattern as its canonical G1 byte.

    Pattern bits are ordered top-left (bit 5) to bottom-right (bit 0)::

        5 4
        3 2
        1 0

    The five low wire bits are the reverse of pattern bits 5..1, and wire
    bit 6 carries pattern bit 0. The full block is normalised to ``0x5F``;
    ``0x7F`` is the obliteration byte and is not emitted.
    """
    if not isinstance(pattern, int) or isinstance(pattern, bool):
        raise TypeError("mosaic pattern must be an int")
    if not 0 <= pattern <= 63:
        raise ValueError("mosaic pattern must be 0..63")
    value = 0x20
    value += ((pattern >> 5) & 1)
    value += ((pattern >> 4) & 1) * 2
    value += ((pattern >> 3) & 1) * 4
    value += ((pattern >> 2) & 1) * 8
    value += ((pattern >> 1) & 1) * 16
    value += (pattern & 1) * 64
    return 0x5F if value == 0x7F else value


def _reverse5(value):
    return (
        ((value & 0x01) << 4)
        | ((value & 0x02) << 2)
        | (value & 0x04)
        | ((value & 0x08) >> 2)
        | ((value & 0x10) >> 4)
    )


def g1_pattern(value):
    """Decode a G1 byte to a 0..63 pattern, or ``None`` if it is not G1.

    ``0x20..0x3F`` and ``0x60..0x7F`` are the canonical ranges. ``0x5F`` and
    ``0x7F`` are both the full block. The observed ``0x40..0x5E`` alias of
    ``0x60..0x7E`` is accepted for capture fidelity; the encoder never emits
    it.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("mosaic byte must be an int")
    if not 0 <= value <= 0x7F:
        raise ValueError("mosaic byte must be 0..0x7F")
    if value == 0x5F:
        return 63
    if 0x20 <= value <= 0x3F:
        return _reverse5(value - 0x20) << 1
    if 0x60 <= value <= 0x7F:
        return (_reverse5(value - 0x60) << 1) | 1
    if 0x40 <= value <= 0x5E:
        return g1_pattern(value | 0x20)
    return None


def repeat_byte(value, count):
    """Repeat a raw byte with ``REP``, without a charset transition."""
    if not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise ValueError("repeat byte must be 0..0xFF")
    if count <= 0:
        return b""
    out = bytearray([value])
    if count == 1:
        return bytes(out)
    remaining = count - 1
    while remaining > 63:
        out.extend([REP, 0x40 + 63])
        remaining -= 63
    if remaining:
        out.extend([REP, 0x40 + remaining])
    return bytes(out)


def mosaic_run(patterns):
    """Encode a sequence of patterns as one G1 run, using ``REP``."""
    patterns = tuple(patterns)
    for pattern in patterns:
        if not isinstance(pattern, int) or isinstance(pattern, bool):
            raise TypeError("mosaic patterns must be ints")
        if not 0 <= pattern <= 63:
            raise ValueError("mosaic patterns must be 0..63")
    out = bytearray()
    index = 0
    while index < len(patterns):
        value = g1_byte(patterns[index])
        end = index + 1
        while end < len(patterns) and g1_byte(patterns[end]) == value:
            end += 1
        out += repeat_byte(value, end - index)
        index = end
    return bytes(out)


_SEXTANT_BRAILLE = (
    "⠁⠈⠉⠂⠃⠊⠋⠐⠑⠘⠙⠒⠓⠚⠛⠄"
    "⠅⠌⠍⠆⠎⠏⠔⠕⠜⠝⠖⠗⠞⠟⠠⠡"
    "⠨⠩⠢⠣⠪⠫⠰⠱⠹⠲⠳⠺⠻⠤⠥⠬"
    "⠭⠦⠧⠮⠯⠴⠵⠼⠽⠶⠷⠾"
)
_MOSAIC_BLOCKS = (
    " ", "▘", "▝", "▀", "▖", "▌", "▞", "▛",
    "▗", "▚", "▐", "▜", "▄", "▙", "▟", "█",
)


def _braille_pattern(braille):
    bits = ord(braille) - 0x2800
    pattern = 0
    if bits & 0x01:
        pattern |= 0x20
    if bits & 0x08:
        pattern |= 0x10
    if bits & 0x02:
        pattern |= 0x08
    if bits & 0x10:
        pattern |= 0x04
    if bits & 0x04:
        pattern |= 0x02
    if bits & 0x20:
        pattern |= 0x01
    return pattern


def _build_mosaic_glyphs():
    glyphs = {0: " ", 21: "▐", 42: "▌", 63: "█"}
    for index, braille in enumerate(_SEXTANT_BRAILLE):
        glyphs.setdefault(_braille_pattern(braille), chr(0x1FB00 + index))
    return glyphs


def _block_glyph(pattern):
    quad = 0
    if pattern & 0x20:
        quad |= 0x01
    if pattern & 0x10:
        quad |= 0x02
    if pattern & 0x02:
        quad |= 0x04
    if pattern & 0x01:
        quad |= 0x08
    glyph = _MOSAIC_BLOCKS[quad]
    if glyph == " ":
        if (pattern & 0x0C) == 0x0C:
            return "▄"
        if pattern & 0x08:
            return "▌"
        if pattern & 0x04:
            return "▐"
    return glyph


_MOSAIC_GLYPHS = _build_mosaic_glyphs()
_MOSAIC_BLOCK_GLYPHS = {
    pattern: _block_glyph(pattern) for pattern in range(64)
}


def mosaic_glyph(pattern, style="sextant"):
    """Return a display glyph for a 0..63 mosaic pattern.

    ``sextant`` uses the Symbols for Legacy Computing sextants, ``blocks`` a
    coarser block-element approximation, and ``plain`` a single placeholder.
    """
    if not isinstance(pattern, int) or isinstance(pattern, bool):
        raise TypeError("mosaic pattern must be an int")
    if not 0 <= pattern <= 63:
        raise ValueError("mosaic pattern must be 0..63")
    if style == "sextant":
        return _MOSAIC_GLYPHS.get(pattern, "▚")
    if style == "blocks":
        return _MOSAIC_BLOCK_GLYPHS[pattern]
    if style == "plain":
        return " " if pattern == 0 else "▚"
    raise ValueError("mosaic style must be 'sextant', 'blocks', or 'plain'")


def cursor(on=True):
    return bytes([CON if on else COF])


def echo_mode(local=True):
    """Select local keyboard echo or route it away from the screen.

    The Minitel echo command is a PRO3 aiguillage frame:
    ``ESC ; <on/off> <modem> <keyboard>``. ``local=True`` turns screen echo
    on; ``local=False`` turns it off so the server can echo.
    """
    return ECHO_ON if local else ECHO_OFF


def scroll_mode(on=True):
    """Select the hardware scroll ("rouleau") or page mode.

    In scroll mode a line feed at row 24 scrolls rows 1-24 up; row 0 is
    untouched.  In page mode the same line feed wraps to row 1.
    """
    return SCROLL_ON if on else SCROLL_OFF


@dataclass(frozen=True)
class Text:
    char: str


@dataclass(frozen=True)
class Enter:
    pass


@dataclass(frozen=True)
class Function:
    name: str


@dataclass(frozen=True)
class Key:
    name: str
    data: bytes = b""


@dataclass(frozen=True)
class Protocol:
    kind: str
    data: bytes


@dataclass(frozen=True)
class Ident:
    data: bytes


@dataclass(frozen=True)
class Control:
    byte: int


class InputParser:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf.extend(data)
        events = []
        i = 0
        n = len(self.buf)
        while i < n:
            b = self.buf[i]
            if b == ESC:
                result = self._esc(i, n, events)
                if result is None:
                    break
                i = result
            elif b == SEP:
                if i + 1 >= n:
                    break
                name = FUNCTION_KEYS.get(self.buf[i + 1])
                if name:
                    events.append(Function(name))
                else:
                    events.append(Control(self.buf[i + 1]))
                i += 2
            elif b == 0x01:
                end = self.buf.find(0x04, i + 1)
                if end < 0:
                    break
                events.append(Ident(bytes(self.buf[i:end + 1])))
                i = end + 1
            elif b == SS2:
                result = self._ss2(i, n, events)
                if result is None:
                    break
                i = result
            elif b == CR:
                events.append(Enter())
                i += 1
            elif 0x20 <= b <= 0x7E:
                events.append(Text(chr(b)))
                i += 1
            else:
                events.append(Control(b))
                i += 1
        self.buf = self.buf[i:]
        return events

    def _esc(self, i, n, events):
        if i + 1 >= n:
            return None
        b = self.buf[i + 1]
        if b == 0x5B:
            j = i + 2
            while j < n:
                if 0x40 <= self.buf[j] <= 0x7E:
                    seq = bytes(self.buf[i:j + 1])
                    final = self.buf[j]
                    if final in ARROWS:
                        events.append(Key(ARROWS[final]))
                    else:
                        name = SPECIAL_KEYS.get(seq)
                        events.append(Key(name) if name else Key("csi", seq))
                    return j + 1
                j += 1
            return None
        if b in (0x39, 0x3A, 0x3B):
            kind = {0x39: "PRO1", 0x3A: "PRO2", 0x3B: "PRO3"}[b]
            extra = {0x39: 1, 0x3A: 2, 0x3B: 3}[b]
            end = i + 2 + extra
            if end > n:
                return None
            events.append(Protocol(kind, bytes(self.buf[i:end])))
            return end
        events.append(Control(b))
        return i + 2

    def _ss2(self, i, n, events):
        if i + 1 >= n:
            return None
        code = self.buf[i + 1]
        if code in SPECIALS_INV:
            events.append(Text(SPECIALS_INV[code]))
            return i + 2
        if i + 2 >= n:
            return None
        base = chr(self.buf[i + 2])
        events.append(Text(ACCENTS_INV.get((code, base), base)))
        return i + 3
