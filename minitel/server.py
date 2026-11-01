"""CLI entrypoint for the example 3615 KILO service."""

import argparse
import asyncio

import pages
import services

from .app import MinitelApp
from .profiles import M1


def missing_service_message(missing):
    return ", ".join(
        f"{key} (pages {', '.join(numbers)})"
        for key, numbers in missing.items()
    )


def main():
    registry = pages.build_registry()
    service_registry = services.build_registry()
    missing = registry.missing_requirements(service_registry)
    if missing:
        raise SystemExit(
            f"missing services: {missing_service_message(missing)}"
        )

    modes = registry.screensaver_groups()
    default_mode = (
        pages.DEFAULT_SCREENSAVER
        if pages.DEFAULT_SCREENSAVER in modes
        else "off"
    )

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
        choices=(*modes, "all", "off"),
        default=default_mode,
        help=f"default screensaver sequence (default: {default_mode})",
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
        default=30.0,
        help="seconds to hold each screensaver page (default: 30)",
    )
    args = ap.parse_args()

    screensaver = (
        None
        if args.screensaver == "off"
        else registry.screensaver_pages(args.screensaver) or None
    )
    app = MinitelApp(
        registry,
        profile=M1,
        initial=pages.INITIAL,
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
        cps=args.cps,
        echo=args.echo,
        services=service_registry,
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
