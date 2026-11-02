"""Weather condition labels for the weather page."""

WEATHER_LABELS = {
    0: "CLEAR",
    1: "MAINLY CLEAR",
    2: "PARTLY CLOUDY",
    3: "OVERCAST",
    45: "FOG",
    48: "FOG",
    51: "DRIZZLE",
    53: "DRIZZLE",
    55: "DRIZZLE",
    56: "ICE DRIZZLE",
    57: "ICE DRIZZLE",
    61: "RAIN",
    63: "RAIN",
    65: "RAIN",
    66: "ICE RAIN",
    67: "ICE RAIN",
    71: "SNOW",
    73: "SNOW",
    75: "SNOW",
    77: "SNOW GRAINS",
    80: "SHOWERS",
    81: "SHOWERS",
    82: "SHOWERS",
    85: "SNOW SHOWERS",
    86: "SNOW SHOWERS",
    95: "THUNDERSTORM",
    96: "STORM HAIL",
    99: "STORM HAIL",
}


def condition_label(code):
    if code is None:
        return "UNKNOWN"
    return WEATHER_LABELS.get(code, "UNKNOWN")
