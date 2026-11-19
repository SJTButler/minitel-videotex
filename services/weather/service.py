"""Open-Meteo weather source and the cached weather service."""

import time
from dataclasses import dataclass

from minitel.data.cache import ResourceCache
from minitel.data.http import get_json
from minitel.data.services import service

BASE_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class Location:
    key: str
    name: str
    code: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class DayForecast:
    date: str
    high: float | None = None
    low: float | None = None
    precipitation: float | None = None
    code: int | None = None


@dataclass(frozen=True)
class Weather:
    place: str
    temperature: float | None = None
    code: int | None = None
    high: float | None = None
    low: float | None = None
    days: tuple[DayForecast, ...] = ()


LOCATIONS = (
    Location("london", "LONDON", "LON", 51.5072, -0.1276),
    Location("paris", "PARIS", "PAR", 48.8566, 2.3522),
    Location("lyon", "LYON", "LYO", 45.7640, 4.8357),
    Location("marseille", "MARSEILLE", "MAR", 43.2965, 5.3698),
)

def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _first_float(value):
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    return _as_float(value)


def _series(value):
    return value if isinstance(value, (list, tuple)) else ()


def _parse_days(daily):
    times = _series(daily.get("time"))
    highs = _series(daily.get("temperature_2m_max"))
    lows = _series(daily.get("temperature_2m_min"))
    rain = _series(daily.get("precipitation_sum"))
    codes = _series(daily.get("weather_code"))
    count = max(
        len(times), len(highs), len(lows), len(rain), len(codes)
    )
    days = []
    for index in range(count):
        days.append(DayForecast(
            date=str(times[index]) if index < len(times) else "",
            high=(
                _as_float(highs[index]) if index < len(highs) else None
            ),
            low=_as_float(lows[index]) if index < len(lows) else None,
            precipitation=(
                _as_float(rain[index]) if index < len(rain) else None
            ),
            code=(
                _as_int(codes[index]) if index < len(codes) else None
            ),
        ))
    return tuple(days)


def parse_weather(payload, place):
    if not isinstance(payload, dict):
        raise ValueError("invalid weather payload")
    current = payload.get("current")
    if not isinstance(current, dict):
        raise ValueError("weather payload has no current conditions")
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        daily = {}
    return Weather(
        place=place,
        temperature=_as_float(
            current.get("temperature_2m", current.get("temperature"))
        ),
        code=_as_int(
            current.get("weather_code", current.get("weathercode"))
        ),
        high=_first_float(daily.get("temperature_2m_max")),
        low=_first_float(daily.get("temperature_2m_min")),
        days=_parse_days(daily),
    )


class WeatherSource:
    def __init__(self, get_json=get_json, timeout=8.0):
        self._get_json = get_json
        self.timeout = timeout

    def weather(self, location):
        url = (
            f"{BASE_URL}?latitude={location.latitude}"
            f"&longitude={location.longitude}"
            "&current=temperature_2m,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,weather_code"
            "&timezone=auto&forecast_days=7"
        )
        payload = self._get_json(url, timeout=self.timeout)
        return parse_weather(payload, location.name)


class WeatherService:
    def __init__(self, source=None, locations=LOCATIONS, ttl=600,
                 retry_delay=60, clock=time.monotonic, thread_factory=None):
        self.source = source or WeatherSource()
        self.locations = tuple(locations)
        self.cache = ResourceCache(
            ttl,
            retry_delay,
            max_entries=max(1, len(self.locations)),
            clock=clock,
            thread_factory=thread_factory,
        )

    async def start(self):
        for location in self.locations:
            self.weather(location)

    async def stop(self):
        return None

    def weather(self, location):
        return self.cache.get(
            location.key, lambda: self.source.weather(location)
        )


@service("weather", description="Open-Meteo current conditions")
def build_weather_service():
    return WeatherService()
