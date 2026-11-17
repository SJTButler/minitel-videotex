"""Page 171: rail path explorer over Realtime Trains data."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from minitel import PAGE_BACK, Region, Screen, codec, page

from pages.common.layout import ACCENT, SECONDARY, WARNING
from pages.common.service_status import (
    ServiceState,
    ServiceStatus,
    describe,
)

PAGE = "171"
PAGE_SIZE = 12
PHASE = "rail_phase"
ORIGIN = "rail_origin"
FILTER = "rail_filter"
BASE = "rail_base"
TRAIN = "rail_train"
ALIGHT = "rail_alight"
PATH = "rail_path"
START = "rail_start"
TOTAL = "rail_total"
STACK = "rail_stack"
ERROR = "rail_error"
FOCUS = "focus"
_CRS = re.compile(r"^[A-Z]{3}$")
LONDON = ZoneInfo("Europe/London")


def _valid(value):
    return bool(_CRS.fullmatch(value))


def _current(ctx):
    return f"{PAGE}#{ctx.extension}" if ctx.extension else PAGE


def _parse_route(token):
    if not token:
        return None
    token = token.strip().upper()
    if len(token) == 3 and _valid(token):
        return token, ""
    if len(token) == 6 and _valid(token[:3]) and _valid(token[3:]):
        return token[:3], token[3:]
    return None


def _minutes(value):
    try:
        hour, minute = str(value).split(":", 1)
        return int(hour) * 60 + int(minute)
    except (TypeError, ValueError):
        return None


def _elapsed(start, end):
    if isinstance(start, datetime) and isinstance(end, datetime):
        return int((end - start).total_seconds() // 60) % (24 * 60)
    first = _minutes(start)
    last = _minutes(end)
    if first is None or last is None:
        return 0
    return (last - first) % (24 * 60)


def _duration(minutes):
    hour, minute = divmod(max(0, int(minutes)), 60)
    return f"{hour}:{minute:02d}"


def _arrival_at(detail, station):
    if detail is None:
        return None
    for stop in detail.stops:
        if stop.code == station:
            return stop.arrival_at
    return None


def _identity_date(unique_identity):
    parts = str(unique_identity).split(":")
    if not parts:
        return None
    try:
        return datetime.strptime(parts[-1], "%Y-%m-%d").date()
    except ValueError:
        return None


def _start_at(departure):
    if departure.scheduled_at is not None:
        return departure.scheduled_at
    day = _identity_date(departure.unique_identity)
    if day is None:
        return None
    try:
        return datetime.combine(
            day,
            datetime.strptime(departure.scheduled, "%H:%M").time(),
            LONDON,
        )
    except ValueError:
        return None


def _calls_after(detail, base):
    if detail is None:
        return ()
    stops = detail.stops
    for index, stop in enumerate(stops):
        if stop.code == base:
            return tuple(stops[index + 1:])
    return tuple(stops)


def _snapshot(ctx):
    return {
        PHASE: ctx.state.get(PHASE),
        ORIGIN: ctx.state.get(ORIGIN),
        FILTER: ctx.state.get(FILTER, ""),
        BASE: ctx.state.get(BASE),
        TRAIN: ctx.state.get(TRAIN),
        ALIGHT: ctx.state.get(ALIGHT),
        PATH: list(ctx.state.get(PATH, [])),
        START: ctx.state.get(START),
        TOTAL: ctx.state.get(TOTAL, 0),
        FOCUS: ctx.focused_region,
    }


def _push_back(ctx):
    stack = list(ctx.state.get(STACK, []))
    stack.append(_snapshot(ctx))
    del stack[:-20]
    ctx.state[STACK] = stack


def _restore(ctx, snapshot):
    for key in (
        PHASE, ORIGIN, FILTER, BASE, TRAIN, ALIGHT, PATH, START, TOTAL,
    ):
        if key == PATH:
            ctx.state[PATH] = list(snapshot.get(PATH, []))
        else:
            ctx.state[key] = snapshot.get(key)
    ctx.focus_region(snapshot.get(FOCUS, "calls"))


def _blank(ctx):
    ctx.set_choice((), region="calls")
    ctx.set_choice((), region="trains")
    screen = Screen()
    ctx.set_status(f"PAGE {PAGE}")
    screen.text(
        1, 0, "RAIL EXPLORER", size=codec.DOUBLE_WIDTH, fg=ACCENT
    )
    screen.text(
        3, 0,
        (ctx.state.get(ERROR) or "USE 171#FROM OR 171#FROMTO")[:40],
        fg=WARNING,
    )
    screen.text(5, 0, "THE PATH IS BUILT BY ENVOI HOPS.", fg=SECONDARY)
    screen.text(6, 0, "RETOUR GOES BACK THROUGH THE PATH.", fg=SECONDARY)
    screen.text(22, 0, "RETOUR=BACK  SOMMAIRE=HOME")
    return screen


def _status(snapshot, *, empty, empty_text="NO ITEMS",
            unavailable="TRAIN DATA UNAVAILABLE"):
    if snapshot is None:
        return ServiceStatus(
            ServiceState.MISSING, "TRAIN DATA NOT CONFIGURED", WARNING
        )
    return describe(
        snapshot,
        empty=empty,
        missing_text="TRAIN DATA NOT CONFIGURED",
        loading_text="LOADING TRAINS...",
        unavailable_text=unavailable,
        empty_text=empty_text,
    )


def _draw_pick(screen, ctx, choice, items, snapshot, origin, filter_to):
    status_info = _status(snapshot, empty=not items, empty_text="NO DEPARTURES")
    screen.text(2, 0, f"PICK A TRAIN FROM {origin}"[:40])
    if filter_to:
        screen.text(3, 0, f"TO {filter_to}"[:40], fg=SECONDARY)
    else:
        screen.text(3, 0, status_info.text[:40], fg=status_info.colour)
    screen.text(
        4, 0,
        f"{'TIME':<5} {'DESTINATION':<21} {'PLT':>3} STATUS",
        fg=SECONDARY,
    )
    for row, _index, departure, selected in choice.rows(items):
        platform = departure.platform or "-"
        screen.text(
            5 + row,
            0,
            (
                f"{departure.scheduled} "
                f"{departure.destination[:21]:<21} "
                f"{platform:>3} {departure.status[:8]}"
            )[:40],
            inverse=selected,
        )
    screen.text(17, 0, choice.label)
    screen.text(19, 0, "PATH " + " > ".join(ctx.state.get(PATH, [])[-5:]))
    screen.text(20, 0, "SOURCE: REALTIME TRAINS", fg=SECONDARY)
    screen.text(21, 0, "ENVOI=TAKE TRAIN")
    screen.text(22, 0, "RETOUR=BACK  SOMMAIRE=HOME")
    return screen


def _draw_explore(
    screen, ctx, calls_choice, calls, trains_choice, trains,
    snapshot, alight, alight_arrival,
):
    train = ctx.state.get(TRAIN)
    base = ctx.state.get(BASE, "")
    if train is not None:
        context = f"{train.scheduled} FROM {base}"
        if alight:
            context = f"{train.scheduled} {base} > {alight}"
        screen.text(2, 0, context[:40])
    if alight:
        status_info = _status(
            snapshot, empty=not trains, empty_text="NO LATER TRAINS"
        )
    else:
        status_info = _status(
            snapshot, empty=not calls, empty_text="NO CALLS"
        )
    screen.text(3, 0, status_info.text[:40], fg=status_info.colour)

    calls_active = ctx.focused_region == "calls"
    screen.text(4, 0, "CALLS", inverse=calls_active)
    right_title = "NO STATION"
    if alight:
        right_title = f"FROM {alight}"
        if alight_arrival:
            label = (
                alight_arrival.strftime("%H:%M")
                if isinstance(alight_arrival, datetime)
                else str(alight_arrival)
            )
            right_title = f"FROM {alight} {label}+"
    screen.text(4, 19, right_title[:21], inverse=not calls_active)
    screen.text(
        5, 0, f"{'TIME':<5} {'STATION':<12}", fg=SECONDARY
    )
    screen.text(
        5, 19,
        f"{'TIME':<5} {'DESTINATION':<11} {'PLT':>3}",
        fg=SECONDARY,
    )
    for row in range(4, 19):
        screen.text(row, 18, "|", fg=SECONDARY)

    for row, _index, stop, selected in calls_choice.rows(calls):
        screen.text(
            6 + row,
            0,
            f"{stop.scheduled} {stop.name[:12]:<12}"[:18],
            inverse=selected,
        )

    if alight:
        for row, _index, departure, selected in trains_choice.rows(trains):
            platform = departure.platform or "-"
            screen.text(
                6 + row,
                19,
                (
                    f"{departure.scheduled} "
                    f"{departure.destination[:11]:<11} "
                    f"{platform:>3}"
                )[:21],
                inverse=selected,
            )
    else:
        screen.text(6, 19, "SELECT A CALLING PT", fg=SECONDARY)

    screen.text(18, 0, calls_choice.label)
    if alight:
        screen.text(18, 19, trains_choice.label)
    path = ctx.state.get(PATH, [])
    total = ctx.state.get(TOTAL, 0)
    suffix = f"  {_duration(total)}" if total else ""
    screen.text(
        20, 0,
        ("PATH " + " > ".join(path[-5:]) + suffix)[:40],
    )
    screen.text(21, 0, "SOURCE: REALTIME TRAINS", fg=SECONDARY)
    if calls_active:
        screen.text(22, 0, "ENVOI=SHOW TRAINS")
    else:
        screen.text(22, 0, "ENVOI=TAKE TRAIN")
    screen.text(23, 0, "RETOUR=BACK  SOMMAIRE=HOME")
    return screen


def _screen(ctx):
    token = ctx.take_extension()
    if token is None and ctx.extension is None:
        ctx.state[PHASE] = "blank"
        ctx.state[ERROR] = "USE 171#FROM OR 171#FROMTO"
        ctx.state[PATH] = []
        ctx.state[START] = None
        ctx.state[TOTAL] = 0
        ctx.state[STACK] = []
    if token is not None:
        route = _parse_route(token)
        if route is None:
            ctx.state[PHASE] = "blank"
            ctx.state[ERROR] = "USE 171#FROM OR 171#FROMTO"
            ctx.state[PATH] = []
            ctx.state[START] = None
            ctx.state[TOTAL] = 0
            ctx.state[STACK] = []
        else:
            origin, filter_to = route
            ctx.state[PHASE] = "pick"
            ctx.state[ORIGIN] = origin
            ctx.state[FILTER] = filter_to
            ctx.state[BASE] = origin
            ctx.state[TRAIN] = None
            ctx.state[ALIGHT] = None
            ctx.state[PATH] = [origin]
            ctx.state[START] = None
            ctx.state[TOTAL] = 0
            ctx.state[STACK] = []
            ctx.state[ERROR] = None

    phase = ctx.state.get(PHASE)
    if phase not in ("pick", "explore"):
        return _blank(ctx)

    origin = ctx.state.get(ORIGIN)
    filter_to = ctx.state.get(FILTER, "")
    service = ctx.service("train")
    configured = service is not None and getattr(service, "configured", False)

    pick_snapshot = None
    calls_snapshot = None
    trains_snapshot = None
    pick_items = ()
    calls = ()
    trains = ()
    detail = None

    if phase == "pick" and configured:
        pick_snapshot = service.departures(origin, filter_to)
        pick_items = (
            pick_snapshot.value.departures
            if pick_snapshot.has_value else ()
        )
    elif phase == "explore" and configured:
        train = ctx.state.get(TRAIN)
        if train is not None:
            calls_snapshot = service.service(train.unique_identity)
            detail = calls_snapshot.value if calls_snapshot.has_value else None
            calls = _calls_after(detail, ctx.state.get(BASE, ""))
        alight = ctx.state.get(ALIGHT)
        if alight and detail is not None:
            arrival = _arrival_at(detail, alight)
            if arrival:
                ctx.state[TOTAL] = _elapsed(
                    ctx.state.get(START), arrival
                )
            trains_snapshot = service.departures(
                alight, time_from=arrival
            )
            board = (
                trains_snapshot.value
                if trains_snapshot.has_value else None
            )
            if board is not None:
                trains = tuple(
                    departure for departure in board.departures
                    if departure.unique_identity != train.unique_identity
                )

    if phase == "pick":
        calls_key = ("pick", origin, filter_to)
        calls_items = pick_items
    else:
        train = ctx.state.get(TRAIN)
        calls_key = train.unique_identity if train is not None else None
        calls_items = calls
    trains_key = ctx.state.get(ALIGHT)

    calls_choice = ctx.set_choice(
        calls_items,
        region="calls",
        key=calls_key,
        commit=None if phase == "pick" else (lambda stop: stop.code),
    )
    trains_choice = ctx.set_choice(
        trains, region="trains", key=trains_key
    )

    screen = Screen()
    ctx.set_status(f"PAGE {PAGE}")
    screen.text(
        1, 0, "RAIL EXPLORER", size=codec.DOUBLE_WIDTH, fg=ACCENT
    )
    if phase == "pick":
        return _draw_pick(
            screen, ctx, calls_choice, pick_items, pick_snapshot,
            origin, filter_to,
        )
    alight_stop = _arrival_at(detail, ctx.state.get(ALIGHT))
    return _draw_explore(
        screen, ctx, calls_choice, calls, trains_choice, trains,
        trains_snapshot or calls_snapshot,
        ctx.state.get(ALIGHT), alight_stop,
    )


def _submit(ctx, line):
    phase = ctx.state.get(PHASE)
    focus = ctx.focused_region
    if focus == "calls":
        committed = ctx.region("calls").committed
        if committed is None:
            return _current(ctx)
        _push_back(ctx)
        if phase == "pick":
            ctx.state[TRAIN] = committed
            ctx.state[BASE] = ctx.state.get(ORIGIN)
            ctx.state[PHASE] = "explore"
            ctx.state[ALIGHT] = None
            ctx.state[PATH] = [ctx.state.get(ORIGIN)]
            ctx.state[START] = _start_at(committed)
            ctx.state[TOTAL] = 0
            ctx.focus_region("calls")
        else:
            station = str(committed).strip().upper()
            if not _valid(station):
                return _current(ctx)
            base = ctx.state.get(BASE, "")
            path = list(ctx.state.get(PATH, []))
            if base in path:
                path = path[:path.index(base) + 1]
            else:
                path = [base] if base else []
            path.append(station)
            ctx.state[PATH] = path
            ctx.state[ALIGHT] = station
            service = ctx.service("train")
            train = ctx.state.get(TRAIN)
            if service is not None and train is not None:
                snapshot = service.service(train.unique_identity)
                detail = snapshot.value if snapshot.has_value else None
                arrival = _arrival_at(detail, station)
                if arrival:
                    ctx.state[TOTAL] = _elapsed(
                        ctx.state.get(START), arrival
                    )
            ctx.focus_region("trains")
        return _current(ctx)

    if focus == "trains":
        committed = ctx.region("trains").committed
        if committed is None:
            return _current(ctx)
        _push_back(ctx)
        alight = ctx.state.get(ALIGHT)
        ctx.state[BASE] = alight
        ctx.state[TRAIN] = committed
        ctx.state[ALIGHT] = None
        path = list(ctx.state.get(PATH, []))
        if not path or path[-1] != alight:
            if alight in path:
                path = path[:path.index(alight) + 1]
            elif alight:
                path.append(alight)
        ctx.state[PATH] = path
        ctx.focus_region("calls")
    return _current(ctx)


def _on_back(ctx):
    stack = list(ctx.state.get(STACK, []))
    if not stack:
        return False
    snapshot = stack.pop()
    ctx.state[STACK] = stack
    _restore(ctx, snapshot)
    return True


@page(
    PAGE,
    title="RAIL EXPLORER",
    requires=("train",),
    extensions=True,
    back_page="170",
    extension_back_page="170",
    on_submit=_submit,
    on_back=_on_back,
    on_tick=_screen,
    tick_interval=1.0,
    regions=(
        Region(
            "calls",
            kind="choice",
            next="trains",
            prev=PAGE_BACK,
            page_size=PAGE_SIZE,
        ),
        Region(
            "trains",
            kind="choice",
            prev=PAGE_BACK,
            page_size=PAGE_SIZE,
        ),
    ),
)
def rail_explorer(ctx):
    return _screen(ctx)
