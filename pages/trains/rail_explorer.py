"""Page 171: rail path explorer over Realtime Trains data."""

from datetime import datetime
from zoneinfo import ZoneInfo

from minitel import PAGE_BACK, Region, Screen, codec, page
from minitel_kit import Rect

from pages.common.layout import ACCENT, SECONDARY, WARNING
from pages.common.service_status import (
    ServiceState,
    ServiceStatus,
    describe,
)
from pages.trains._support.crs import parse_route, valid_crs
from pages.trains._support.departures import (
    calls_header,
    calls_row,
    right_header,
    right_row,
    train_header,
    train_row,
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
LONDON = ZoneInfo("Europe/London")


def _current(ctx):
    return f"{PAGE}#{ctx.extension}" if ctx.extension else PAGE


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
        PHASE: ctx.page_state.get(PHASE),
        ORIGIN: ctx.page_state.get(ORIGIN),
        FILTER: ctx.page_state.get(FILTER, ""),
        BASE: ctx.page_state.get(BASE),
        TRAIN: ctx.page_state.get(TRAIN),
        ALIGHT: ctx.page_state.get(ALIGHT),
        PATH: list(ctx.page_state.get(PATH, [])),
        START: ctx.page_state.get(START),
        TOTAL: ctx.page_state.get(TOTAL, 0),
        FOCUS: ctx.focused_region,
    }


def _push_back(ctx):
    stack = list(ctx.page_state.get(STACK, []))
    stack.append(_snapshot(ctx))
    del stack[:-20]
    ctx.page_state[STACK] = stack


def _restore(ctx, snapshot):
    for key in (
        PHASE, ORIGIN, FILTER, BASE, TRAIN, ALIGHT, PATH, START, TOTAL,
    ):
        if key == PATH:
            ctx.page_state[PATH] = list(snapshot.get(PATH, []))
        else:
            ctx.page_state[key] = snapshot.get(key)
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
        (ctx.page_state.get(ERROR) or "USE 171#FROM OR 171#FROMTO")[:40],
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
    train_header(screen, 4)
    for row, _index, departure, selected in choice.rows(items):
        train_row(screen, 5 + row, departure, inverse=selected)
    screen.text(17, 0, choice.label)
    screen.text(19, 0, "PATH " + " > ".join(ctx.page_state.get(PATH, [])[-5:]))
    screen.text(20, 0, "SOURCE: REALTIME TRAINS", fg=SECONDARY)
    screen.text(21, 0, "ENVOI=TAKE TRAIN")
    screen.text(22, 0, "RETOUR=BACK  SOMMAIRE=HOME")
    return screen


def _draw_explore(
    screen, ctx, calls_choice, calls, trains_choice, trains,
    snapshot, alight, alight_arrival,
):
    train = ctx.page_state.get(TRAIN)
    base = ctx.page_state.get(BASE, "")
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
    left = Rect(4, 0, 17, 18)
    right = Rect(4, 19, 17, 21)
    left.text(screen, 0, 0, "CALLS", inverse=calls_active)
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
    right.text(screen, 0, 0, right_title, inverse=not calls_active)
    calls_header(screen, 5)
    right_header(screen, 5, col=19)
    for row in range(4, 19):
        screen.text(row, 18, "|", fg=SECONDARY)

    for row, _index, stop, selected in calls_choice.rows(calls):
        calls_row(screen, 6 + row, stop, inverse=selected)

    if alight:
        for row, _index, departure, selected in trains_choice.rows(trains):
            right_row(screen, 6 + row, departure, col=19, inverse=selected)
    else:
        right.text(screen, 2, 0, "SELECT A CALLING PT", fg=SECONDARY)

    left.text(screen, 14, 0, calls_choice.label)
    if alight:
        right.text(screen, 14, 0, trains_choice.label)
    path = ctx.page_state.get(PATH, [])
    total = ctx.page_state.get(TOTAL, 0)
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
        ctx.page_state[PHASE] = "blank"
        ctx.page_state[ERROR] = "USE 171#FROM OR 171#FROMTO"
        ctx.page_state[PATH] = []
        ctx.page_state[START] = None
        ctx.page_state[TOTAL] = 0
        ctx.page_state[STACK] = []
    if token is not None:
        route = parse_route(token)
        if route is None:
            ctx.page_state[PHASE] = "blank"
            ctx.page_state[ERROR] = "USE 171#FROM OR 171#FROMTO"
            ctx.page_state[PATH] = []
            ctx.page_state[START] = None
            ctx.page_state[TOTAL] = 0
            ctx.page_state[STACK] = []
        else:
            origin, filter_to = route
            ctx.page_state[PHASE] = "pick"
            ctx.page_state[ORIGIN] = origin
            ctx.page_state[FILTER] = filter_to
            ctx.page_state[BASE] = origin
            ctx.page_state[TRAIN] = None
            ctx.page_state[ALIGHT] = None
            ctx.page_state[PATH] = [origin]
            ctx.page_state[START] = None
            ctx.page_state[TOTAL] = 0
            ctx.page_state[STACK] = []
            ctx.page_state[ERROR] = None

    phase = ctx.page_state.get(PHASE)
    if phase not in ("pick", "explore"):
        return _blank(ctx)

    origin = ctx.page_state.get(ORIGIN)
    filter_to = ctx.page_state.get(FILTER, "")
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
        train = ctx.page_state.get(TRAIN)
        if train is not None:
            calls_snapshot = service.service(train.unique_identity)
            detail = calls_snapshot.value if calls_snapshot.has_value else None
            calls = _calls_after(detail, ctx.page_state.get(BASE, ""))
        alight = ctx.page_state.get(ALIGHT)
        if alight and detail is not None:
            arrival = _arrival_at(detail, alight)
            if arrival:
                ctx.page_state[TOTAL] = _elapsed(
                    ctx.page_state.get(START), arrival
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
        train = ctx.page_state.get(TRAIN)
        calls_key = train.unique_identity if train is not None else None
        calls_items = calls
    trains_key = ctx.page_state.get(ALIGHT)

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
    alight_stop = _arrival_at(detail, ctx.page_state.get(ALIGHT))
    return _draw_explore(
        screen, ctx, calls_choice, calls, trains_choice, trains,
        trains_snapshot or calls_snapshot,
        ctx.page_state.get(ALIGHT), alight_stop,
    )


def _submit(ctx, line):
    phase = ctx.page_state.get(PHASE)
    focus = ctx.focused_region
    if focus == "calls":
        committed = ctx.region("calls").committed
        if committed is None:
            return _current(ctx)
        _push_back(ctx)
        if phase == "pick":
            ctx.page_state[TRAIN] = committed
            ctx.page_state[BASE] = ctx.page_state.get(ORIGIN)
            ctx.page_state[PHASE] = "explore"
            ctx.page_state[ALIGHT] = None
            ctx.page_state[PATH] = [ctx.page_state.get(ORIGIN)]
            ctx.page_state[START] = _start_at(committed)
            ctx.page_state[TOTAL] = 0
            ctx.focus_region("calls")
        else:
            station = str(committed).strip().upper()
            if not valid_crs(station):
                return _current(ctx)
            base = ctx.page_state.get(BASE, "")
            path = list(ctx.page_state.get(PATH, []))
            if base in path:
                path = path[:path.index(base) + 1]
            else:
                path = [base] if base else []
            path.append(station)
            ctx.page_state[PATH] = path
            ctx.page_state[ALIGHT] = station
            service = ctx.service("train")
            train = ctx.page_state.get(TRAIN)
            if service is not None and train is not None:
                snapshot = service.service(train.unique_identity)
                detail = snapshot.value if snapshot.has_value else None
                arrival = _arrival_at(detail, station)
                if arrival:
                    ctx.page_state[TOTAL] = _elapsed(
                        ctx.page_state.get(START), arrival
                    )
            ctx.focus_region("trains")
        return _current(ctx)

    if focus == "trains":
        committed = ctx.region("trains").committed
        if committed is None:
            return _current(ctx)
        _push_back(ctx)
        alight = ctx.page_state.get(ALIGHT)
        ctx.page_state[BASE] = alight
        ctx.page_state[TRAIN] = committed
        ctx.page_state[ALIGHT] = None
        path = list(ctx.page_state.get(PATH, []))
        if not path or path[-1] != alight:
            if alight in path:
                path = path[:path.index(alight) + 1]
            elif alight:
                path.append(alight)
        ctx.page_state[PATH] = path
        ctx.focus_region("calls")
    return _current(ctx)


def _on_back(ctx):
    stack = list(ctx.page_state.get(STACK, []))
    if not stack:
        return False
    snapshot = stack.pop()
    ctx.page_state[STACK] = stack
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
    tick_interval=30.0,
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
