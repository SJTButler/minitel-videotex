#!/usr/bin/env python3
"""Interactive Minitel terminal client.

Connect to a local Minitel server, decode Videotex bytes into the 25x40 grid,
and drive the server with local keys.

Examples:
    python3 tools/minitel_client.py --connect 127.0.0.1:3615
    python3 tools/minitel_client.py --connect 127.0.0.1:3615 --no-local-echo
"""

import argparse
import curses
import locale
import os
import select
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from minitel import codec
from virtual_minitel import Decoder

ROWS = codec.ROWS
COLS = codec.COLS

FUNCTION_BYTES = {
    name: bytes([codec.SEP, value])
    for value, name in codec.FUNCTION_KEYS.items()
}
ARROW_BYTES = {
    name: bytes([codec.ESC, ord("["), value])
    for value, name in codec.ARROWS.items()
}

SPECIAL_KEYS = {
    "\n": bytes([codec.CR]),
    "\r": bytes([codec.CR]),
    "\t": FUNCTION_BYTES["SUITE"],
    "\x08": FUNCTION_BYTES["CORRECTION"],
    "\x7f": FUNCTION_BYTES["CORRECTION"],
    "\x1b": FUNCTION_BYTES["ANNULATION"],
    curses.KEY_ENTER: bytes([codec.CR]),
    curses.KEY_BACKSPACE: FUNCTION_BYTES["CORRECTION"],
    0x08: FUNCTION_BYTES["CORRECTION"],
    0x7F: FUNCTION_BYTES["CORRECTION"],
    27: FUNCTION_BYTES["ANNULATION"],
    curses.KEY_BTAB: FUNCTION_BYTES["RETOUR"],
    curses.KEY_PPAGE: FUNCTION_BYTES["RETOUR"],
    curses.KEY_NPAGE: FUNCTION_BYTES["SUITE"],
    curses.KEY_HOME: FUNCTION_BYTES["SOMMAIRE"],
    curses.KEY_END: FUNCTION_BYTES["ENVOI"],
    curses.KEY_DC: FUNCTION_BYTES["ANNULATION"],
    curses.KEY_UP: ARROW_BYTES["up"],
    curses.KEY_DOWN: ARROW_BYTES["down"],
    curses.KEY_LEFT: ARROW_BYTES["left"],
    curses.KEY_RIGHT: ARROW_BYTES["right"],
    curses.KEY_F1: FUNCTION_BYTES["GUIDE"],
    curses.KEY_F2: FUNCTION_BYTES["SOMMAIRE"],
    curses.KEY_F3: FUNCTION_BYTES["RETOUR"],
    curses.KEY_F4: FUNCTION_BYTES["SUITE"],
    curses.KEY_F5: FUNCTION_BYTES["ENVOI"],
    curses.KEY_F6: FUNCTION_BYTES["ANNULATION"],
    curses.KEY_F7: FUNCTION_BYTES["CORRECTION"],
    curses.KEY_F8: FUNCTION_BYTES["REPETITION"],
}

HELP_KEY = curses.KEY_F9
QUIT_KEYS = {curses.KEY_F10, 0x11, 0x03, "\x11", "\x03"}

HELP_LINES = (
    "MINITEL TERMINAL CLIENT",
    "",
    "ENTER      ENVOI",
    "BACKSPACE  CORRECTION",
    "ESC        ANNULATION",
    "TAB        SUITE",
    "SHIFT+TAB  RETOUR",
    "ARROWS     CURSOR KEYS",
    "",
    "F1 GUIDE   F2 HOME",
    "F3 BACK    F4 NEXT",
    "F5 SEND    F6 CANCEL",
    "F7 CORRECT F8 REPEAT",
    "F9 CLOSE   ^Q QUIT",
)


def printable_char(key, uppercase=True):
    if not isinstance(key, str) or len(key) != 1:
        return None
    if key in ("\n", "\r", "\t") or not key.isprintable():
        return None
    if uppercase and key.isascii() and key.isalpha():
        key = key.upper()
    try:
        codec.text(key)
    except ValueError:
        return None
    return key


def key_to_bytes(key, uppercase=True):
    if isinstance(key, str):
        if key in SPECIAL_KEYS:
            return SPECIAL_KEYS[key]
        char = printable_char(key, uppercase)
        if char is None:
            return b""
        return codec.text(char)
    if isinstance(key, int):
        return SPECIAL_KEYS.get(key, b"")
    return b""


def echo_to_screen(screen, char):
    if char:
        screen.put(char)


def parse_address(value):
    host, separator, port_text = value.rpartition(":")
    if not separator:
        return value, 3615
    host = host or "127.0.0.1"
    try:
        port = int(port_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 0 < port < 65536:
        raise argparse.ArgumentTypeError("port must be 1..65535")
    return host, port


class Client:
    def __init__(self, host, port, *, local_echo=True, uppercase=True):
        self.host = host
        self.port = port
        self.local_echo = local_echo
        self.uppercase = uppercase
        self.sock = None
        self.decoder = None
        self.connected = False
        self.error = ""

    def connect(self):
        self.close()
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5)
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                sock.close()
                raise
        except OSError as exc:
            self.error = " ".join(str(exc).split())
            return False
        self.sock = sock
        self.decoder = Decoder()
        self.connected = True
        self.error = ""
        return True

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.connected = False

    def disconnect(self, reason):
        self.error = " ".join(str(reason).split())
        self.close()

    def status(self):
        echo = "ON" if self.local_echo else "OFF"
        if self.connected:
            return (
                f"{self.host}:{self.port} ECHO:{echo} "
                "F9=HELP ^Q=QUIT"
            )
        if self.error:
            return f"DISCONNECTED: {self.error} R=RECONNECT ^Q=QUIT"
        return "DISCONNECTED R=RECONNECT ^Q=QUIT"

    def send_key(self, key):
        data = key_to_bytes(key, self.uppercase)
        if not data or not self.connected or self.sock is None:
            return False
        try:
            self.sock.sendall(data)
        except OSError as exc:
            self.disconnect(exc)
            return True
        char = printable_char(key, self.uppercase)
        if self.local_echo and char is not None and self.decoder is not None:
            echo_to_screen(self.decoder.screen, char)
            return True
        return False

    def read_available(self):
        if not self.connected or self.sock is None:
            return False
        changed = False
        for _ in range(64):
            try:
                readable, _, _ = select.select([self.sock], [], [], 0)
            except (OSError, ValueError) as exc:
                self.disconnect(exc)
                return True
            if not readable:
                break
            try:
                data = self.sock.recv(4096)
            except OSError as exc:
                self.disconnect(exc)
                return True
            if not data:
                self.disconnect("server closed")
                return True
            self.decoder.feed(data)
            changed = True
        return changed


class View:
    def __init__(self, stdscr, *, mono=False, wide=True):
        self.stdscr = stdscr
        self.mono = mono
        self.wide = wide
        self.colour = False
        self.pairs = set()
        self.stdscr.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        if not mono:
            try:
                if curses.has_colors():
                    curses.start_color()
                    limit = getattr(curses, "COLOR_PAIRS", 0)
                    for fg in range(8):
                        for bg in range(8):
                            pair = self._pair(fg, bg)
                            if limit and pair >= limit:
                                continue
                            try:
                                curses.init_pair(pair, fg, bg)
                            except curses.error:
                                continue
                            self.pairs.add(pair)
                    self.colour = bool(self.pairs)
            except curses.error:
                self.colour = False

    @staticmethod
    def _pair(fg, bg):
        return 1 + fg * 8 + bg

    def _cell_attr(self, cell):
        attrs = 0
        if self.colour:
            fg, bg = cell.fg, cell.bg
            if cell.inverse:
                fg, bg = bg, fg
            pair = self._pair(fg, bg)
            if pair in self.pairs:
                attrs |= curses.color_pair(pair)
            elif cell.inverse:
                attrs |= curses.A_REVERSE
        else:
            if cell.fg != codec.BLACK:
                attrs |= curses.A_BOLD
            if cell.inverse:
                attrs |= curses.A_REVERSE
            if self.mono:
                if cell.fg in (1, 4):
                    attrs |= curses.A_DIM
                elif cell.fg in (3, 6, 7):
                    attrs |= curses.A_BOLD
        if cell.underline:
            attrs |= curses.A_UNDERLINE
        if cell.flash:
            attrs |= curses.A_BLINK
        if cell.size in (codec.DOUBLE_HEIGHT, codec.DOUBLE_SIZE):
            attrs |= curses.A_BOLD
        return attrs

    def _glyph(self, cell, x):
        if cell.size in (codec.DOUBLE_WIDTH, codec.DOUBLE_SIZE):
            if x + 1 < COLS:
                if cell.ch == " ":
                    return "  ", 2
                if self.wide and 0x21 <= ord(cell.ch) <= 0x7E:
                    return chr(ord(cell.ch) + 0xFEE0), 2
                return cell.ch + " ", 2
        return cell.ch, 1

    def _physical_col(self, screen, row, col):
        x = 0
        for index in range(col):
            _, width = self._glyph(screen.rows[row][index], x)
            x += width
        return min(x, COLS - 1)

    def _draw_grid(self, screen):
        for row in range(ROWS):
            col = 0
            x = 0
            while col < COLS:
                if x >= COLS:
                    break
                attr = self._cell_attr(screen.rows[row][col])
                start = x
                parts = []
                while col < COLS:
                    if x >= COLS:
                        break
                    cell = screen.rows[row][col]
                    if self._cell_attr(cell) != attr:
                        break
                    glyph, width = self._glyph(cell, x)
                    parts.append(glyph)
                    x += width
                    col += 1
                if parts:
                    try:
                        self.stdscr.addstr(row, start, "".join(parts), attr)
                    except curses.error:
                        pass

    def _draw_status(self, status, row=ROWS):
        text = status[:COLS]
        try:
            self.stdscr.addnstr(
                row, 0, " " * COLS, COLS, curses.A_REVERSE
            )
            self.stdscr.addnstr(
                row, 0, text, COLS, curses.A_REVERSE
            )
        except curses.error:
            pass

    def _draw_help(self, height):
        for index, line in enumerate(HELP_LINES):
            if index >= height:
                break
            try:
                attr = curses.A_BOLD if index == 0 else 0
                self.stdscr.addnstr(index, 0, line, COLS, attr)
            except curses.error:
                pass

    def _draw_small(self, width, height):
        lines = (
            f"NEED {COLS}x{ROWS}",
            f"HAVE {width}x{height}",
            "RESIZE OR ^Q",
        )
        for index, line in enumerate(lines):
            if index >= height:
                break
            try:
                self.stdscr.addnstr(index, 0, line, COLS)
            except curses.error:
                pass

    def _place_cursor(self, screen):
        try:
            if not screen.cursor:
                curses.curs_set(0)
                return
            row = min(max(screen.row, 0), ROWS - 1)
            col = min(max(screen.col, 0), COLS - 1)
            curses.curs_set(1)
            self.stdscr.move(row, self._physical_col(screen, row, col))
        except curses.error:
            pass

    def draw(self, screen, status, help_mode=False, force_status=False):
        try:
            height, width = self.stdscr.getmaxyx()
            self.stdscr.erase()
            if width < COLS or height < ROWS:
                self._draw_small(width, height)
                curses.curs_set(0)
            elif help_mode:
                self._draw_help(height)
                curses.curs_set(0)
            else:
                self._draw_grid(screen)
                if height > ROWS:
                    self._draw_status(status, ROWS)
                elif force_status:
                    self._draw_status(status, ROWS - 1)
                self._place_cursor(screen)
            self.stdscr.noutrefresh()
            curses.doupdate()
        except curses.error:
            pass


def run(stdscr, args):
    view = View(stdscr, mono=args.mono, wide=args.wide)
    client = Client(
        args.connect[0],
        args.connect[1],
        local_echo=args.local_echo,
        uppercase=not args.lowercase,
    )
    client.connect()
    stdscr.timeout(30)
    dirty = True
    help_mode = False
    last_draw = 0.0
    last_bell = client.decoder.screen.bell if client.decoder else 0
    try:
        while True:
            key = None
            try:
                key = stdscr.get_wch()
            except curses.error:
                key = None
            except KeyboardInterrupt:
                break
            if key == -1:
                key = None
            if key is not None:
                dirty = True
                last_draw = 0.0
                if key in QUIT_KEYS:
                    break
                if key == HELP_KEY:
                    help_mode = not help_mode
                elif help_mode:
                    help_mode = False
                elif (
                    isinstance(key, str)
                    and key.lower() == "r"
                    and not client.connected
                ):
                    client.connect()
                    last_bell = (
                        client.decoder.screen.bell
                        if client.decoder
                        else 0
                    )
                elif client.connected:
                    if client.send_key(key):
                        dirty = True
            if client.read_available():
                dirty = True
                if client.decoder is not None:
                    bell = client.decoder.screen.bell
                    if bell != last_bell:
                        curses.beep()
                        last_bell = bell
            now = time.monotonic()
            if dirty and (last_draw == 0.0 or now - last_draw >= 0.03):
                screen = (
                    client.decoder.screen
                    if client.decoder
                    else Decoder().screen
                )
                view.draw(
                    screen,
                    client.status(),
                    help_mode=help_mode,
                    force_status=not client.connected,
                )
                dirty = False
                last_draw = now
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Interactive terminal client for a Minitel server"
    )
    ap.add_argument(
        "--connect",
        type=parse_address,
        default=("127.0.0.1", 3615),
        metavar="HOST:PORT",
        help="server address (default: 127.0.0.1:3615)",
    )
    ap.add_argument(
        "--local-echo",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="echo printable keys locally; disable when the server runs --echo",
    )
    ap.add_argument(
        "--lowercase",
        action="store_true",
        help="send typed case instead of uppercasing ASCII letters",
    )
    ap.add_argument(
        "--wide",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use fullwidth glyphs for double-width text",
    )
    ap.add_argument(
        "--mono",
        action="store_true",
        help="approximate the Minitel 1 grey display",
    )
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    os.environ.setdefault("ESCDELAY", "25")
    try:
        curses.wrapper(run, args)
    except (curses.error, OSError) as exc:
        print(f"minitel_client: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
