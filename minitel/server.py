"""CLI entrypoint for the example 3615 KILO service."""

import argparse
import asyncio

import pages
from pages.manifest import DEFAULT_SCREENSAVER, SCREENSAVER_MODES

from .app import MinitelApp
from .profiles import M1


def main():
    ap = argparse.ArgumentParser(description="Minitel 1 Videotex server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=3615)
    ap.add_argument(
        "--cps",
        type=float,
        default=None,
        help="pacing in chars/s; default 1200/9; 0 disables pacing",
    )
    ap.add_argument(
        "--echo",
        action="store_true",
        help="echo typed characters from the server (local echo off)",
    )
    ap.add_argument(
        "--screensaver",
        choices=(*SCREENSAVER_MODES, "off"),
        default=DEFAULT_SCREENSAVER,
        help=f"default screensaver sequence (default: {DEFAULT_SCREENSAVER})",
    )
    ap.add_argument(
        "--screensaver-after",
        type=float,
        default=120.0,
        help="idle seconds before the screensaver; 0 disables auto (default: 120)",
    )
    ap.add_argument(
        "--screensaver-hold",
        type=float,
        default=20.0,
        help="seconds to hold each screensaver page (default: 20)",
    )
    args = ap.parse_args()

    registry = pages.build_registry()
    screensaver = (
        None
        if args.screensaver == "off"
        else SCREENSAVER_MODES[args.screensaver]
    )
    app = MinitelApp(
        registry,
        profile=M1,
        initial=pages.INITIAL,
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
        cps=args.cps,
        echo=args.echo,
        services=pages.build_services(),
        screensaver=screensaver,
        screensaver_after=args.screensaver_after,
        screensaver_hold=args.screensaver_hold,
    )
    asyncio.run(app.serve(args.host, args.port))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
