"""Page 170: train departures from a station."""

from minitel import Region, Screen, codec, page

from pages.common.layout import ACCENT, SECONDARY, WARNING
from pages.common.service_status import (
    ServiceState,
    ServiceStatus,
    describe,
)
from pages.common.widgets import line_field
from pages.trains._support.crs import parse_route, valid_crs

PAGE = "170"
PAGE_SIZE = 8
QUERY = "train_query"
ERROR = "train_error"


def _screen(ctx):
    token = ctx.take_extension()
    route = parse_route(token) if token is not None else None
    if token is not None:
        if route is None:
            ctx.state[ERROR] = "USE 170#FROMTO"
            ctx.state.pop(QUERY, None)
            ctx.values["origin"] = ""
            ctx.values["destination"] = ""
        else:
            ctx.state[QUERY] = route
            ctx.state.pop(ERROR, None)
            ctx.values["origin"] = route[0]
            ctx.values["destination"] = route[1]

    origin, destination = ctx.state.get(QUERY, ("", ""))
    query_key = (origin, destination) if origin else None
    if token is not None:
        if route is None:
            ctx.focus("origin")
        else:
            ctx.focus_region("results")
    if ctx.focused_region == "results":
        if origin and not ctx.values.get("origin"):
            ctx.values["origin"] = origin
        if destination and not ctx.values.get("destination"):
            ctx.values["destination"] = destination

    screen = Screen()
    ctx.set_status(f"PAGE {PAGE}")
    screen.text(
        1, 0, "TRAIN TIMES", size=codec.DOUBLE_WIDTH, fg=ACCENT
    )
    line_field(
        screen, ctx, "origin", 2, 6, 3, label="FROM:", region="form"
    )
    line_field(
        screen, ctx, "destination", 2, 15, 3, label="TO:",
        label_col=11, region="form",
    )

    service = ctx.service("train")
    board = None
    departures = ()
    if not origin:
        state = ServiceStatus(
            ServiceState.MISSING, "TYPE A FROM CODE", SECONDARY
        )
    elif service is None or not getattr(service, "configured", False):
        state = ServiceStatus(
            ServiceState.MISSING, "TRAIN DATA NOT CONFIGURED", WARNING
        )
    else:
        snapshot = service.departures(origin, destination)
        board = snapshot.value if snapshot.has_value else None
        departures = board.departures if board is not None else ()
        state = describe(
            snapshot,
            empty=not departures,
            missing_text="TRAIN DATA NOT CONFIGURED",
            loading_text="LOADING TRAINS...",
            unavailable_text="TRAIN DATA UNAVAILABLE",
            empty_text=(
                f"NO DIRECT TO {destination}"
                if destination else "NO DEPARTURES"
            ),
        )
    error = ctx.state.get(ERROR)
    if error:
        state = ServiceStatus(ServiceState.MISSING, error, WARNING)

    pager = ctx.set_pager(departures, region="results", key=query_key)
    if board is not None:
        where = board.station
        if destination:
            resolved = (
                service.station_name(destination)
                if service is not None else None
            )
            where = f"{where} TO {resolved or destination}"
        screen.text(3, 0, where[:40], fg=SECONDARY)
    screen.text(4, 0, state.text[:40], fg=state.colour)
    screen.text(
        5, 0,
        f"{'TIME':<5} {'DESTINATION':<21} {'PLT':>3} STATUS",
        fg=SECONDARY,
    )
    for row, _index, departure in pager.rows(departures):
        platform = departure.platform or "-"
        screen.text(
            6 + row,
            0,
            (
                f"{departure.scheduled} "
                f"{departure.destination[:21]:<21} "
                f"{platform:>3} {departure.status[:8]}"
            )[:40],
        )
    screen.text(15, 0, pager.label)
    if destination and not departures:
        screen.text(
            16, 0, "DIRECT SERVICES ONLY; CLEAR TO FOR ALL",
            fg=SECONDARY,
        )
    if board is not None and board.degraded:
        screen.text(17, 0, board.degraded[:40], fg=WARNING)
    screen.text(20, 0, "SOURCE: REALTIME TRAINS", fg=SECONDARY)
    if ctx.focused_region == "results":
        screen.text(21, 0, "ENVOI=REFRESH  SUITE=NEXT PAGE")
    else:
        screen.text(21, 0, "ENVOI=SEARCH  SUITE=NEXT FIELD")
    screen.text(22, 0, "RETOUR=BACK  SOMMAIRE=HOME")
    return screen


def _submit(ctx, values):
    origin = values.get("origin", "").strip().upper()
    destination = values.get("destination", "").strip().upper()
    if not valid_crs(origin):
        ctx.state[ERROR] = "USE 3-LETTER CRS CODES"
        ctx.focus("origin")
        return PAGE
    if destination and not valid_crs(destination):
        ctx.state[ERROR] = "USE 3-LETTER CRS CODES"
        ctx.focus("destination")
        return PAGE
    ctx.state[QUERY] = (origin, destination)
    ctx.state.pop(ERROR, None)
    ctx.focus_region("results")
    return PAGE


@page(
    PAGE,
    title="TRAIN TIMES",
    aliases=("7",),
    requires=("train",),
    form=True,
    on_form=_submit,
    on_tick=_screen,
    tick_interval=1.0,
    no_screensaver=True,
    back_page="100",
    extensions=True,
    extension_back_page="100",
    regions=(
        Region("form", kind="form", next="results"),
        Region(
            "results",
            kind="pager",
            prev="form",
            activate="stay",
            page_size=PAGE_SIZE,
        ),
    ),
)
def train_times(ctx):
    return _screen(ctx)
