"""Page 120: current conditions and today's forecast."""

from minitel import codec
from minitel.pages import page
from minitel.screen import Screen

from ..layout import SECONDARY, WARNING, footer, page_input, status, updated_label


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
            f"{weather.condition[:13]:<13} "
            f"{_degrees(weather.low):>3}/{_degrees(weather.high):<3}"
        )
    if snapshot.error is not None:
        return f"{location.name:<10}  --  NO DATA"
    return f"{location.name:<10}  --  LOADING..."


def _status_text(snapshots):
    if not snapshots:
        return "NO WEATHER LOCATIONS"
    values = [s for _, s in snapshots if s.has_value and s.value is not None]
    errors = [s for _, s in snapshots if s.error is not None]
    if values:
        latest = max(values, key=lambda s: s.loaded_at or 0)
        label = "UPDATED " + updated_label(latest)
        if errors:
            label = "OFFLINE - CACHED " + updated_label(latest)
        return label
    if any(s.loading for _, s in snapshots):
        return "LOADING WEATHER..."
    if errors:
        return "WEATHER UNAVAILABLE"
    return "LOADING WEATHER..."


def _status_colour(text):
    if text.startswith(
        ("NOT CONFIGURED", "UNAVAILABLE", "OFFLINE", "NO WEATHER")
    ):
        return WARNING
    return SECONDARY


def weather_screen(ctx):
    s = Screen()
    status(s, "PAGE 120")
    s.text(1, 0, "WEATHER", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(2, 0, "CURRENT CONDITIONS", fg=SECONDARY)

    s.text(
        4,
        0,
        "CITY       NOW  SKY          LOW/HIGH",
        fg=SECONDARY,
        underline=True,
    )

    service = ctx.services.get("weather")
    if service is None:
        s.text(5, 0, "WEATHER SERVICE NOT CONFIGURED", fg=WARNING)
        status_text = "WEATHER NOT CONFIGURED"
    else:
        snapshots = [
            (location, service.weather(location))
            for location in service.locations
        ]
        for index, (location, snapshot) in enumerate(snapshots[:4]):
            s.text(5 + index, 0, _row(location, snapshot)[:codec.COLS])
        status_text = _status_text(snapshots)

    s.rule(10, 0, codec.COLS, "-")
    s.text(11, 0, "LOW/HIGH = TODAY'S FORECAST", fg=SECONDARY)
    s.text(12, 0, "SOURCE: OPEN-METEO", fg=SECONDARY)
    s.text(13, 0, status_text[:codec.COLS], fg=_status_colour(status_text))
    page_input(s, ctx)
    footer(s)
    return s


@page("120", title="WEATHER", aliases=("2",), tick_interval=30.0,
      on_tick=weather_screen)
def weather(ctx):
    return weather_screen(ctx)
