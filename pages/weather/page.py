"""Page 120: current conditions, today's forecast, and city detail."""

from minitel.protocol import codec
from minitel.pagemodel import page
from minitel.render import Screen
from minitel.text import fit

from ..common.layout import SECONDARY, WARNING, footer, key_footer
from ..common.service_status import describe_many
from ..common.widgets import page_input
from ._support.labels import condition_label


def _temperature(value):
    if value is None:
        return "--"
    return f"{round(value)}C"


def _degrees(value):
    if value is None:
        return "--"
    return str(round(value))


def _row(location, snapshot):
    if snapshot.has_value and snapshot.value is not None:
        weather = snapshot.value
        return (
            f"{location.name:<10} {_temperature(weather.temperature):>4}  "
            f"{condition_label(weather.code)[:13]:<13} "
            f"{_degrees(weather.low):>3}/{_degrees(weather.high):<3}"
        )
    if snapshot.error is not None:
        return f"{location.name:<10}  --  NO DATA"
    return f"{location.name:<10}  --  LOADING..."


def _status(snapshots):
    return describe_many(
        (snapshot for _, snapshot in snapshots),
        missing_text="NO WEATHER LOCATIONS",
        loading_text="LOADING WEATHER...",
        unavailable_text="WEATHER UNAVAILABLE",
    )


def _location(service, code):
    for location in service.locations:
        if location.code.upper() == code:
            return location
    return None


def _direct_codes(service):
    return " ".join(
        f"120#{location.code}" for location in service.locations
    )


def weather_summary(ctx):
    s = Screen()
    ctx.set_status("PAGE 120")
    s.text(1, 0, "WEATHER", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(2, 0, "CURRENT CONDITIONS", fg=SECONDARY)

    s.text(
        4,
        0,
        "CITY       NOW  SKY          LOW/HIGH",
        fg=SECONDARY,
        underline=True,
    )

    service = ctx.service("weather")
    if service is None:
        s.text(5, 0, "WEATHER SERVICE NOT CONFIGURED", fg=WARNING)
        page_status = describe_many(
            (), missing_text="WEATHER NOT CONFIGURED"
        )
    else:
        snapshots = [
            (location, service.weather(location))
            for location in service.locations
        ]
        for index, (location, snapshot) in enumerate(snapshots[:4]):
            s.text(5 + index, 0, _row(location, snapshot)[:codec.COLS])
        page_status = _status(snapshots)

    s.rule(10, 0, codec.COLS, "-")
    s.text(11, 0, "LOW/HIGH = TODAY'S FORECAST", fg=SECONDARY)
    s.text(12, 0, "SOURCE: OPEN-METEO", fg=SECONDARY)
    s.text(13, 0, page_status.text[:codec.COLS], fg=page_status.colour)
    if service is not None and service.locations:
        s.text(
            14,
            0,
            fit(f"DIRECT: {_direct_codes(service)}", codec.COLS),
            fg=SECONDARY,
        )
    page_input(s, ctx)
    footer(s)
    return s


def weather_detail(ctx):
    s = Screen()
    ctx.set_status(f"PAGE 120#{ctx.extension}")
    s.text(1, 0, "WEATHER", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(2, 0, "CITY DETAIL", fg=SECONDARY)

    service = ctx.service("weather")
    if service is None:
        s.text(4, 0, "WEATHER SERVICE NOT CONFIGURED", fg=WARNING)
        page_input(s, ctx)
        key_footer(s, ("RETOUR=WEATHER", "SOMMAIRE=HOME"))
        return s

    location = _location(service, ctx.extension)
    if location is None:
        s.text(
            4,
            0,
            fit(f"NO CITY: {ctx.extension}", codec.COLS),
            fg=WARNING,
        )
        s.text(
            6,
            0,
            fit(f"TRY {_direct_codes(service)}", codec.COLS),
            fg=SECONDARY,
        )
        page_input(s, ctx)
        key_footer(s, ("RETOUR=WEATHER", "SOMMAIRE=HOME"))
        return s

    snapshot = service.weather(location)
    s.text(4, 0, location.name, inverse=True)
    if snapshot.has_value and snapshot.value is not None:
        weather = snapshot.value
        s.text(6, 0, f"NOW: {_temperature(weather.temperature)}")
        s.text(
            7,
            0,
            fit(f"SKY: {condition_label(weather.code)}", codec.COLS),
        )
        s.text(
            8,
            0,
            f"LOW/HIGH: {_degrees(weather.low)}/{_degrees(weather.high)}",
        )
    elif snapshot.error is not None:
        s.text(6, 0, "NO DATA", fg=WARNING)
    else:
        s.text(6, 0, "LOADING...", fg=WARNING)

    s.rule(10, 0, codec.COLS, "-")
    s.text(11, 0, "SOURCE: OPEN-METEO", fg=SECONDARY)
    page_status = _status([(location, snapshot)])
    s.text(13, 0, page_status.text[:codec.COLS], fg=page_status.colour)
    page_input(s, ctx)
    key_footer(s, ("RETOUR=WEATHER", "SOMMAIRE=HOME"))
    return s


def weather_screen(ctx):
    if ctx.extension:
        return weather_detail(ctx)
    return weather_summary(ctx)


@page(
    "120",
    title="WEATHER",
    aliases=("2",),
    requires=("weather",),
    tick_interval=30.0,
    on_tick=weather_screen,
    extensions=True,
    extension_back_page="120",
)
def weather(ctx):
    return weather_screen(ctx)
