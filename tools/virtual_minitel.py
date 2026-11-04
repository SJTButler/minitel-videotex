#!/usr/bin/env python3
"""Decode a Videotex byte stream into a 25x40 grid.

Examples:
    python3 tools/virtual_minitel.py --demo
    python3 tools/virtual_minitel.py --file research/captures/page.bin
    python3 tools/virtual_minitel.py --connect 127.0.0.1:3615
"""

import argparse
import os
import socket
import sys

ROWS = 25
COLS = 40

FG_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

SPECIALS = {
    0x23: "£",
    0x30: "°",
    0x3C: "¼",
    0x3D: "½",
    0x3E: "¾",
    0x2C: "←",
    0x2D: "↑",
    0x2E: "→",
    0x2F: "↓",
    0x6A: "Œ",
    0x7A: "œ",
    0x7B: "ß",
}

ACCENTS = {
    (0x41, "a"): "à", (0x42, "a"): "á", (0x43, "a"): "â", (0x48, "a"): "ä",
    (0x41, "e"): "è", (0x42, "e"): "é", (0x43, "e"): "ê", (0x48, "e"): "ë",
    (0x41, "i"): "ì", (0x42, "i"): "í", (0x43, "i"): "î", (0x48, "i"): "ï",
    (0x41, "o"): "ò", (0x42, "o"): "ó", (0x43, "o"): "ô", (0x48, "o"): "ö",
    (0x41, "u"): "ù", (0x42, "u"): "ú", (0x43, "u"): "û", (0x48, "u"): "ü",
    (0x4B, "c"): "ç",
}


class Cell:
    __slots__ = ("ch", "fg", "bg", "inverse", "flash", "underline", "size", "charset")

    def __init__(self, ch=" ", fg=7, bg=0, inverse=False, flash=False,
                 underline=False, size=0, charset=0):
        self.ch = ch
        self.fg = fg
        self.bg = bg
        self.inverse = inverse
        self.flash = flash
        self.underline = underline
        self.size = size
        self.charset = charset

    def clone(self, ch=None):
        return Cell(
            ch=self.ch if ch is None else ch,
            fg=self.fg, bg=self.bg, inverse=self.inverse,
            flash=self.flash, underline=self.underline,
            size=self.size, charset=self.charset,
        )


class Screen:
    def __init__(self):
        self.rows = [[Cell() for _ in range(COLS)] for _ in range(ROWS)]
        self.pen = Cell()
        self.row = 1
        self.col = 0
        self.cursor = False
        self.last_ch = " "
        self.bell = 0
        self.scroll_mode = False

    def clear(self):
        self.rows = [[Cell() for _ in range(COLS)] for _ in range(ROWS)]
        self.pen = Cell()
        self.last_ch = " "
        self.row = 1
        self.col = 0

    def pos(self, row, col):
        self.row = max(0, min(ROWS - 1, row))
        self.col = max(0, min(COLS - 1, col))

    def reset_pen(self):
        self.pen = Cell()

    def put(self, ch):
        if self.col >= COLS:
            self.col = 0
            self.line_feed()
        cell = self.pen.clone(ch)
        cell.charset = self.pen.charset
        self.rows[self.row][self.col] = cell
        self.last_ch = ch
        self.col += 1

    def repeat(self, count):
        for _ in range(count):
            self.put(self.last_ch)

    def _blank_row(self):
        return [self.pen.clone(" ") for _ in range(COLS)]

    def _scroll_up(self):
        for row in range(1, ROWS - 1):
            self.rows[row] = self.rows[row + 1]
        self.rows[ROWS - 1] = self._blank_row()

    def _scroll_down(self):
        for row in range(ROWS - 1, 1, -1):
            self.rows[row] = self.rows[row - 1]
        self.rows[1] = self._blank_row()

    def line_feed(self):
        if self.row < ROWS - 1:
            self.row += 1
            return
        if self.scroll_mode:
            self._scroll_up()
        else:
            self.row = 1

    def vertical_tab(self):
        if self.row > 1:
            self.row -= 1
            return
        if self.row == 1 and self.scroll_mode:
            self._scroll_down()
        elif self.row == 1:
            self.row = ROWS - 1

    def can(self):
        for c in range(self.col, COLS):
            self.rows[self.row][c] = self.pen.clone(" ")

    def text(self):
        out = []
        for r in range(ROWS):
            out.append("".join(cell.ch for cell in self.rows[r]))
        return "\n".join(out)


class Decoder:
    def __init__(self):
        self.screen = Screen()
        self.buf = bytearray()

    def feed(self, data):
        self.buf.extend(data)
        i = 0
        n = len(self.buf)
        while i < n:
            b = self.buf[i]
            if b == 0x1B:
                consumed, i = self._esc(i)
                if consumed == 0:
                    break
            elif b == 0x1F:
                if i + 2 >= n:
                    break
                row = self.buf[i + 1] - 0x40
                col = self.buf[i + 2] - 0x40 - 1
                self.screen.pos(row, col)
                self.screen.reset_pen()
                i += 3
            elif b == 0x19:
                consumed, i = self._ss2(i)
                if consumed == 0:
                    break
            elif b == 0x12:
                if i + 1 >= n:
                    break
                self.screen.repeat(self.buf[i + 1] - 0x40)
                i += 2
            elif b == 0x01:
                end = self.buf.find(0x04, i + 1)
                if end < 0:
                    break
                i = end + 1
            elif b == 0x0C:
                self.screen.clear()
                i += 1
            elif b == 0x1E:
                self.screen.pos(1, 0)
                self.screen.reset_pen()
                i += 1
            elif b == 0x18:
                self.screen.can()
                i += 1
            elif b == 0x0E:
                self.screen.pen.charset = 1
                i += 1
            elif b == 0x0F:
                self.screen.pen.charset = 0
                i += 1
            elif b == 0x11:
                self.screen.cursor = True
                i += 1
            elif b == 0x14:
                self.screen.cursor = False
                i += 1
            elif b == 0x0D:
                self.screen.col = 0
                i += 1
            elif b == 0x08:
                self.screen.col = max(0, self.screen.col - 1)
                i += 1
            elif b == 0x0A:
                self.screen.line_feed()
                i += 1
            elif b == 0x0B:
                self.screen.vertical_tab()
                i += 1
            elif b == 0x07:
                self.screen.bell += 1
                i += 1
            elif 0x20 <= b <= 0x7E:
                if self.screen.pen.charset == 1:
                    self.screen.put("▚")
                else:
                    self.screen.put(chr(b))
                i += 1
            else:
                i += 1
        self.buf = self.buf[i:]

    def _esc(self, i):
        n = len(self.buf)
        if i + 1 >= n:
            return 0, i
        b = self.buf[i + 1]
        if b == 0x39:
            if i + 2 >= n:
                return 0, i
            return 3, i + 3
        if b == 0x3A:
            if i + 3 >= n:
                return 0, i
            command = self.buf[i + 2]
            argument = self.buf[i + 3]
            if argument == 0x43 and command in (0x69, 0x6A):
                self.screen.scroll_mode = command == 0x69
            return 4, i + 4
        if b == 0x3B:
            if i + 4 >= n:
                return 0, i
            return 5, i + 5
        if b == 0x5B:
            j = i + 2
            while j < n:
                if 0x40 <= self.buf[j] <= 0x7E:
                    return j - i + 1, j + 1
                j += 1
            return 0, i
        p = self.screen.pen
        if 0x40 <= b <= 0x47:
            p.fg = b - 0x40
        elif 0x50 <= b <= 0x57:
            p.bg = b - 0x50
        elif b == 0x48:
            p.flash = True
        elif b == 0x49:
            p.flash = False
        elif b == 0x5D:
            p.inverse = True
        elif b == 0x5C:
            p.inverse = False
        elif b == 0x5A:
            p.underline = True
        elif b == 0x59:
            p.underline = False
        elif b == 0x4C:
            p.size = 0
        elif b == 0x4D:
            p.size = 1
        elif b == 0x4E:
            p.size = 2
        elif b == 0x4F:
            p.size = 3
        return 2, i + 2

    def _ss2(self, i):
        n = len(self.buf)
        if i + 1 >= n:
            return 0, i
        code = self.buf[i + 1]
        if code in SPECIALS:
            self.screen.put(SPECIALS[code])
            return 2, i + 2
        if i + 2 >= n:
            return 0, i
        base = chr(self.buf[i + 2])
        self.screen.put(ACCENTS.get((code, base), base))
        return 3, i + 3


def ansi_cell(cell):
    fg = cell.fg
    bg = cell.bg
    if cell.inverse:
        fg, bg = bg, fg
    codes = [f"3{fg}", f"4{bg}"]
    if cell.underline:
        codes.append("4")
    if cell.flash:
        codes.append("5")
    return "\x1b[" + ";".join(codes) + "m" + cell.ch + "\x1b[0m"


def render(screen, color):
    lines = []
    for r in range(ROWS):
        if color:
            line = "".join(ansi_cell(cell) for cell in screen.rows[r])
        else:
            line = "".join(cell.ch for cell in screen.rows[r])
        lines.append(f"{r:02d} |{line}|")
    lines.append("")
    lines.append(
        f"cursor=({screen.row},{screen.col}) visible={screen.cursor} "
        f"fg={FG_NAMES[screen.pen.fg]} bg={FG_NAMES[screen.pen.bg]} "
        f"size={screen.pen.size} bell={screen.bell}"
    )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Decode Videotex bytes into a 25x40 grid")
    ap.add_argument("--demo", action="store_true", help="decode hello.first_page()")
    ap.add_argument("--file", help="read raw bytes from a file")
    ap.add_argument("--connect", help="host:port to connect to and read once")
    ap.add_argument("--plain", action="store_true", help="no ANSI colour")
    ap.add_argument("--ansi", action="store_true", help="force ANSI colour")
    args = ap.parse_args()

    if args.demo:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from hello import first_page
        data = first_page()
    elif args.file:
        with open(args.file, "rb") as f:
            data = f.read()
    elif args.connect:
        host, port = args.connect.rsplit(":", 1)
        sock = socket.create_connection((host, int(port)), timeout=5)
        sock.settimeout(0.6)
        chunks = []
        while True:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
        sock.close()
        data = b"".join(chunks)
    else:
        data = sys.stdin.buffer.read()

    decoder = Decoder()
    decoder.feed(data)
    color = args.ansi or (sys.stdout.isatty() and not args.plain)
    print(render(decoder.screen, color))


if __name__ == "__main__":
    main()
