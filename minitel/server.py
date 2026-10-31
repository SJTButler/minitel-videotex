"""CLI entrypoint for the example 3615 KILO service."""

import argparse
import asyncio

import pages

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
    args = ap.parse_args()

    registry = pages.build_registry()
    app = MinitelApp(
        registry,
        profile=M1,
        initial=pages.INITIAL,
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
        cps=args.cps,
        echo=args.echo,
    )
    asyncio.run(app.serve(args.host, args.port))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
