"""CLI entrypoint for the example 3615 KILO service."""

import argparse
import asyncio
import sys

import pages
import services

from minitel.app import MinitelApp
from minitel.terminal.power import POWER_OFF, POWER_ON, PowerSignals
from minitel.terminal.profiles import M1


def missing_service_message(missing):
    return ", ".join(
        f"{key} (pages {', '.join(numbers)})"
        for key, numbers in missing.items()
    )


def override_lines(overrides):
    lines = []
    for event in overrides:
        old = f"{event.old_source or '?'}/{event.old_page.number}"
        new = f"{event.new_source or '?'}/{event.new_page.number}"
        if event.kind == "page":
            new_aliases = set(event.new_page.aliases)
            moved = [
                alias
                for alias in event.old_page.aliases
                if alias in new_aliases
            ]
            removed = [
                alias
                for alias in event.old_page.aliases
                if alias not in new_aliases
            ]
            detail = ""
            if moved:
                detail += f"; aliases moved: {', '.join(moved)}"
            if removed:
                detail += f"; aliases removed: {', '.join(removed)}"
            lines.append(f"page {event.key}: {old} -> {new}{detail}")
        else:
            lines.append(f"alias {event.key}: {old} -> {new}")
    return lines


def override_report(registry):
    if not registry.overrides:
        return ""
    lines = override_lines(registry.overrides)
    return "page composition overrides:\n" + "\n".join(
        f"  {line}" for line in lines
    )


def load_registries(pages_packages=(), services_packages=(), extra_paths=()):
    for path in reversed(tuple(extra_paths)):
        sys.path.insert(0, path)
    try:
        page_registry = pages.build_registry(*pages_packages)
    except ModuleNotFoundError as exc:
        raise SystemExit(f"cannot load pages package(s): {exc}") from exc
    try:
        service_registry = services.build_registry(*services_packages)
    except ModuleNotFoundError as exc:
        raise SystemExit(f"cannot load services package(s): {exc}") from exc
    return page_registry, service_registry


def main():
    ap = argparse.ArgumentParser(description="Minitel 1 Videotex server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=3615)
    ap.add_argument(
        "--pages-package",
        action="append",
        default=[],
        metavar="NAME",
        help="additional page package to discover (repeatable)",
    )
    ap.add_argument(
        "--services-package",
        action="append",
        default=[],
        metavar="NAME",
        help="additional service package to discover (repeatable)",
    )
    ap.add_argument(
        "--extra-path",
        action="append",
        default=[],
        metavar="PATH",
        help="prepend PATH to sys.path before loading extra packages",
    )
    ap.add_argument(
        "--strict-overrides",
        action="store_true",
        help="fail instead of warning when a later package overrides a page or alias",
    )
    ap.add_argument(
        "--cps",
        type=float,
        default=None,
        help="pacing in chars/s; default 1200/9; 0 disables pacing",
    )
    ap.add_argument(
        "--echo",
        dest="echo",
        action="store_true",
        default=True,
        help="echo typed characters from the server (default; local echo off)",
    )
    ap.add_argument(
        "--local-echo",
        dest="echo",
        action="store_false",
        help="use the terminal's local echo; the server does not echo",
    )
    ap.add_argument(
        "--screensaver",
        default=None,
        help=(
            "screensaver sequence; the default is the public clock group, "
            "or off when unavailable"
        ),
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
    ap.add_argument(
        "--power-off",
        default=POWER_OFF.hex(),
        help="hex bytes for terminal power-off; empty disables (default: 00)",
    )
    ap.add_argument(
        "--power-on",
        default=POWER_ON.hex(),
        help=(
            "hex bytes for terminal power-on; empty disables "
            f"(default: {POWER_ON.hex()})"
        ),
    )
    ap.add_argument(
        "--no-power-pause",
        action="store_true",
        help="ignore power-off; keep the power-on full repaint",
    )
    ap.add_argument(
        "--no-power",
        action="store_true",
        help="disable terminal power detection entirely",
    )
    args = ap.parse_args()

    registry, service_registry = load_registries(
        args.pages_package, args.services_package, args.extra_path
    )
    missing = registry.missing_requirements(service_registry)
    if missing:
        raise SystemExit(
            f"missing services: {missing_service_message(missing)}"
        )

    report = override_report(registry)
    if report:
        if args.strict_overrides:
            raise SystemExit(f"strict overrides enabled:\n{report}")
        print(f"WARNING: {report}", file=sys.stderr, flush=True)

    modes = registry.screensaver_groups()
    default_mode = (
        pages.DEFAULT_SCREENSAVER
        if pages.DEFAULT_SCREENSAVER in modes
        else "off"
    )
    if args.screensaver is None:
        args.screensaver = default_mode
    if args.screensaver not in (*modes, "all", "off"):
        choices = ", ".join((*modes, "all", "off"))
        raise SystemExit(
            f"invalid screensaver {args.screensaver!r}; choose from: {choices}"
        )

    try:
        if args.no_power:
            power = PowerSignals(off=b"", on=b"")
        else:
            power = PowerSignals(
                off=b"" if args.no_power_pause else bytes.fromhex(args.power_off),
                on=bytes.fromhex(args.power_on),
            )
    except ValueError as exc:
        raise SystemExit(f"invalid power byte sequence: {exc}") from exc

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
        power=power,
    )
    asyncio.run(app.serve(args.host, args.port))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
