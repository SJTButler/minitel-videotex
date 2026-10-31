#!/usr/bin/env python3
"""First-light TCP server for Minitel Telnet Pro.

Run:
    python3 tools/hello.py --port 3615

Point the dongle's Telnet preset at <this machine's LAN IP>:3615.
The server sends a known Videotex page and logs every key byte.
"""

import argparse
import asyncio
import socket
import time

COF = 0x14
CON = 0x11
FF = 0x0C
US = 0x1F
CAN = 0x18
ESC = 0x1B
REP = 0x12
SEP = 0x13
CR = 0x0D

FUNCTION_KEYS = {
    0x41: "ENVOI",
    0x42: "RETOUR",
    0x43: "REPETITION",
    0x44: "GUIDE",
    0x45: "ANNULATION",
    0x46: "SOMMAIRE",
    0x47: "CORRECTION",
    0x48: "SUITE",
    0x49: "CONNEXION/FIN",
}

PROBE = bytes([
    ESC, 0x39, 0x7B,
    ESC, 0x39, 0x70,
    ESC, 0x39, 0x74,
    ESC, 0x3A, 0x73,
])

TYPE_NAMES = {
    0x62: "Minitel 1",
    0x63: "Minitel 1",
    0x72: "Minitel 1 / 1 Dialogue",
    0x73: "Minitel 1 Couleur",
    0x75: "Minitel 1B",
    0x76: "Minitel 2 (mono or colour)",
    0x77: "Minitel 10B",
    0x79: "Minitel 5",
    0x7A: "Minitel 12",
}

SPEED_CODES = {0x52: 300, 0x64: 1200, 0x76: 4800, 0x7F: 9600}


def pos(row, col):
    return bytes([US, 0x40 + row, 0x40 + col])


def attr(code):
    return bytes([ESC, code])


def repeat(ch, n):
    return ch + bytes([REP, 0x40 + n - 1])


def first_page(title="HELLO 3615"):
    out = bytearray()
    out += bytes([COF])
    out += pos(0, 1) + bytes([CAN])
    out += bytes([FF])
    out += pos(1, 1) + attr(0x5D) + attr(0x4E) + title.encode("ascii")
    out += attr(0x5C) + attr(0x4C)
    out += pos(3, 1) + b"FIRST LIGHT"
    out += pos(5, 1) + repeat(b"=", 40)
    out += pos(7, 1) + b"ACCENTS: " + bytes([0x19, 0x42, 0x65]) + b" " + bytes([0x19, 0x4B, 0x63])
    out += pos(10, 1) + b"TYPE A LINE, THEN ENVOI:"
    out += pos(12, 1) + attr(0x5D) + b" " * 30 + attr(0x5C)
    out += pos(12, 1) + bytes([CON])
    return bytes(out)


def response_page(line):
    safe = "".join(ch if 0x20 <= ord(ch) <= 0x7E else "?" for ch in line)[:30]
    out = bytearray()
    out += bytes([COF])
    out += pos(0, 1) + bytes([CAN])
    out += bytes([FF])
    out += pos(1, 1) + attr(0x5D) + attr(0x4E) + b"ENVOI"
    out += attr(0x5C) + attr(0x4C)
    out += pos(3, 1) + b"LINE: " + safe.encode("ascii")
    out += pos(5, 1) + b"SOMMAIRE TO RESET"
    out += pos(10, 1) + b"TYPE ANOTHER LINE:"
    out += pos(12, 1) + attr(0x5D) + b" " * 30 + attr(0x5C)
    out += pos(12, 1) + bytes([CON])
    return bytes(out)


class KeyParser:
    def __init__(self, log):
        self.log = log
        self.state = 0
        self.skip = 0
        self.pro = 0
        self.frame = []
        self.csi = []
        self.line = ""
        self.events = []

    def feed(self, data):
        self.events = []
        for b in data:
            self.byte(b)
        return self.events

    def byte(self, b):
        if self.state == 0:
            if b == ESC:
                self.state = 1
            elif b == SEP:
                self.state = 2
            elif b == 0x01:
                self.state = 6
                self.frame = [b]
            elif b == CR:
                self.log("ENTER")
            elif b == 0x12:
                self.log("REP/RESET 0x12")
            elif 0x20 <= b <= 0x7E:
                self.line += chr(b)
                self.log(f"TEXT {chr(b)!r} line={self.line!r}")
            else:
                self.log(f"CTRL 0x{b:02X}")
        elif self.state == 1:
            if b == 0x5B:
                self.state = 3
                self.csi = []
            elif b == 0x39:
                self.state = 4
                self.pro = 1
                self.skip = 1
                self.frame = [ESC, b]
            elif b == 0x3A:
                self.state = 4
                self.pro = 2
                self.skip = 2
                self.frame = [ESC, b]
            elif b == 0x3B:
                self.state = 4
                self.pro = 3
                self.skip = 3
                self.frame = [ESC, b]
            else:
                self.log(f"ESC 0x{b:02X}")
                self.state = 0
        elif self.state == 2:
            name = FUNCTION_KEYS.get(b, f"FUNCTION 0x{b:02X}")
            self.log(name)
            if name == "ENVOI":
                self.events.append(("ENVOI", self.line))
            elif name == "CORRECTION":
                self.line = self.line[:-1]
                self.log(f"CORRECT line={self.line!r}")
            elif name == "ANNULATION":
                self.line = ""
                self.log("CANCEL")
            elif name == "SOMMAIRE":
                self.line = ""
                self.events.append(("SOMMAIRE", None))
            elif name == "RETOUR":
                self.line = ""
                self.events.append(("RETOUR", None))
            self.state = 0
        elif self.state == 3:
            if 0x20 <= b <= 0x3F:
                self.csi.append(b)
            else:
                seq = " ".join(f"{x:02X}" for x in self.csi + [b])
                self.log(f"CSI {seq}")
                self.state = 0
        elif self.state == 4:
            self.frame.append(b)
            self.skip -= 1
            if self.skip <= 0:
                seq = " ".join(f"{x:02X}" for x in self.frame)
                detail = ""
                if self.pro == 2 and len(self.frame) >= 4:
                    cmd, arg = self.frame[2], self.frame[3]
                    if cmd == 0x75:
                        detail = f" -> speed {SPEED_CODES.get(arg, arg)}"
                    elif cmd == 0x73:
                        detail = (
                            f" -> mode 0x{arg:02X}"
                            f" 80col={bool(arg & 1)}"
                            f" scroll={bool(arg & 2)}"
                            f" pce={bool(arg & 4)}"
                            f" lowercase={bool(arg & 8)}"
                        )
                self.log(f"PRO{self.pro} {seq}{detail}")
                self.state = 0
        elif self.state == 6:
            self.frame.append(b)
            if b == 0x04:
                seq = " ".join(f"{x:02X}" for x in self.frame)
                detail = ""
                if len(self.frame) >= 5:
                    mfr, typ, ver = self.frame[1], self.frame[2], self.frame[3]
                    detail = (
                        f" -> {TYPE_NAMES.get(typ, f'type 0x{typ:02X}')}"
                        f" mfr=0x{mfr:02X} ver=0x{ver:02X}"
                    )
                self.log(f"IDENT {seq}{detail}")
                self.state = 0


async def handle(reader, writer, cps):
    peer = writer.get_extra_info("peername")
    sock = writer.get_extra_info("socket")
    if sock is not None:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    print(f"[connect] {peer}", flush=True)

    def log(message):
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp}] {peer} {message}", flush=True)

    parser = KeyParser(log)
    out = first_page()
    writer.write(out)
    await writer.drain()
    log(f"SENT first page ({len(out)} bytes)")
    writer.write(PROBE)
    await writer.drain()
    log("SENT probe: IDENT + STATUS + SPEED + MODE")
    log("Try: type a line + ENVOI, then SOMMAIRE")

    delay = 1.0 / cps if cps > 0 else 0.0
    while True:
        data = await reader.read(64)
        if not data:
            break
        log("RX " + " ".join(f"{b:02X}" for b in data))
        for name, value in parser.feed(data):
            if name == "ENVOI":
                reply = response_page(value)
                for i in range(0, len(reply), 32):
                    writer.write(reply[i:i + 32])
                    await writer.drain()
                    if delay:
                        await asyncio.sleep(delay)
                log(f"SENT response ({len(reply)} bytes), line={value!r}")
                parser.line = ""
            elif name == "SOMMAIRE":
                writer.write(first_page())
                await writer.drain()
                log("SENT first page (SOMMAIRE)")
            elif name == "RETOUR":
                writer.write(first_page())
                await writer.drain()
                log("SENT first page (RETOUR)")

    print(f"[disconnect] {peer}", flush=True)
    writer.close()
    await writer.wait_closed()


def lan_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


async def main():
    ap = argparse.ArgumentParser(description="First-light Minitel TCP server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=3615)
    ap.add_argument("--cps", type=float, default=0.0,
                    help="pacing in chars/s; 0 = no pacing (fine for this small page)")
    args = ap.parse_args()

    server = await asyncio.start_server(
        lambda r, w: handle(r, w, args.cps), args.host, args.port
    )
    print(f"listening on {args.host}:{args.port}", flush=True)
    ips = lan_ips()
    if ips:
        print("Candidate LAN IPs: " + ", ".join(ips), flush=True)
    else:
        print("Find this machine's LAN IP with: ip -4 addr show", flush=True)
    print("Point the dongle's Telnet preset at <that IP>:%d" % args.port, flush=True)
    print("Dongle: col80=false, prestel=false. Server profile: colour=false for your mono M2.", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
