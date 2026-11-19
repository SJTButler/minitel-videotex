"""Page 121: seven-day weather chart."""

from datetime import date

from minitel import Screen, codec, page
from minitel.text import fit
from minitel_kit import Bars, Sparkline

from ..common.layout import SECONDARY, WARNING, key_footer
from ..common.widgets import page_input
from .page import _location, _status

CHART_COL = 6
CHART_WIDTH = codec.COLS - CHART_COL
AXIS_COL = CHART_COL - 1


def _axis(s, top, bottom, top_text, middle_text, bottom_text, middle_row):
    for row in range(top, bottom + 1):
        s.put(row, AXIS_COL, "|", fg=SECONDARY)
    s.put(top, AXIS_COL, "+", fg=SECONDARY)
    s.put(middle_row, AXIS_COL, "+", fg=SECONDARY)
    s.put(bottom, AXIS_COL, "+", fg=SECONDARY)
    s.text(top, 0, top_text, fg=SECONDARY)
    s.text(middle_row, 0, middle_text, fg=SECONDARY)
    s.text(bottom, 0, bottom_text, fg=SECONDARY)


def _codes(service):
    return " ".join(f"121#{location.code}" for location in service.locations)


def _day_label(value):
    try:
        return date.fromisoformat(value).strftime("%a").upper()[:3]
    except (TypeError, ValueError):
        return "???"


def _series(days, name):
    return tuple(getattr(day, name) for day in days)


def _title(ctx):
    if ctx.extension:
        return f"PAGE 121#{ctx.extension.upper()}"
    return "PAGE 121"


def _footer(s):
    key_footer(s, ("RETOUR=WEATHER", "SOMMAIRE=HOME"))


def weather_chart_screen(ctx):
    s = Screen()
    ctx.set_status(_title(ctx))
    s.text(1, 0, "WEATHER CHART", inverse=True, size=codec.DOUBLE_WIDTH)

    service = ctx.service("weather")
    if service is None:
        s.text(3, 0, "WEATHER SERVICE NOT CONFIGURED", fg=WARNING)
        page_input(s, ctx)
        _footer(s)
        return s

    if ctx.extension:
        location = _location(service, ctx.extension)
        if location is None:
            s.text(
                3,
                0,
                fit(f"NO CITY: {ctx.extension}", codec.COLS),
                fg=WARNING,
            )
            s.text(
                5,
                0,
                fit("TRY " + _codes(service), codec.COLS),
                fg=SECONDARY,
            )
            page_input(s, ctx)
            _footer(s)
            return s
    elif service.locations:
        location = service.locations[0]
    else:
        location = None

    if location is None:
        s.text(3, 0, "NO WEATHER LOCATIONS", fg=WARNING)
        page_input(s, ctx)
        _footer(s)
        return s

    snapshot = service.weather(location)
    s.text(
        2,
        0,
        fit(f"{location.name}  7-DAY OUTLOOK", codec.COLS),
        fg=SECONDARY,
    )

    status = _status([(location, snapshot)])
    s.text(19, 0, status.text[:codec.COLS], fg=status.colour)
    s.text(
        21,
        0,
        fit("DIRECT: " + _codes(service), codec.COLS),
        fg=SECONDARY,
    )
    page_input(s, ctx)
    _footer(s)

    if not snapshot.has_value or snapshot.value is None:
        message = "LOADING WEATHER..." if snapshot.loading else "NO FORECAST"
        s.text(4, 0, message, fg=WARNING)
        return s

    days = snapshot.value.days
    if not days:
        s.text(4, 0, "NO FORECAST DATA", fg=WARNING)
        return s

    highs = _series(days, "high")
    lows = _series(days, "low")
    rain = _series(days, "precipitation")
    usable = [
        value
        for value in highs + lows
        if value is not None
    ]
    if usable:
        low = min(usable)
        high = max(usable)
        if high <= low:
            high = low + 1
        s.text(3, CHART_COL, "HIGH", fg=codec.WHITE)
        s.text(3, CHART_COL + 6, "LOW", fg=SECONDARY)
        middle = round((low + high) / 2)
        _axis(
            s,
            4,
            11,
            f"{round(high):>3}C",
            f"{middle:>3}C",
            f"{round(low):>3}C",
            8,
        )
        Sparkline(
            CHART_WIDTH, 8, minimum=low, maximum=high, fg=codec.WHITE
        ).draw(s, 4, CHART_COL, highs)
        Sparkline(
            CHART_WIDTH, 8, minimum=low, maximum=high, fg=SECONDARY
        ).draw(s, 4, CHART_COL, lows)
        count = min(len(days), 7)
        for index in range(count):
            column = (
                CHART_COL + (CHART_WIDTH - 3) // 2
                if count == 1
                else CHART_COL
                + round(index * (CHART_WIDTH - 3) / (count - 1))
            )
            s.text(
                12,
                column,
                _day_label(days[index].date),
                fg=SECONDARY,
            )
    else:
        s.text(4, 0, "NO TEMPERATURE DATA", fg=WARNING)

    rain_values = rain[:7]
    usable_rain = [value for value in rain_values if value is not None]
    if usable_rain:
        peak = max(1, max(usable_rain))
        s.text(13, CHART_COL, "PRECIPITATION MM", fg=SECONDARY)
        _axis(
            s,
            14,
            18,
            f"{round(peak):>3}",
            f"{round(peak / 2):>3}",
            f"{0:>3}",
            16,
        )
        Bars(
            CHART_WIDTH,
            5,
            minimum=0,
            maximum=peak,
            gap=1,
            fg=SECONDARY,
        ).draw(s, 14, CHART_COL, rain_values)
    else:
        s.text(13, 0, "NO PRECIPITATION DATA", fg=SECONDARY)

    return s


@page(
    "121",
    title="WEATHER CHART",
    requires=("weather",),
    back_page="120",
    extensions=True,
    extension_back_page="120",
    tick_interval=300.0,
    on_tick=weather_chart_screen,
)
def weather_chart(ctx):
    return weather_chart_screen(ctx)
