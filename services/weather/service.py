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
class Weather:
    place: str
    temperature: float | None = None
    code: int | None = None
    high: float | None = None
    low: float | None = None


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
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=auto&forecast_days=1"
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
