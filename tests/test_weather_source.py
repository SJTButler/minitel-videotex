import asyncio
import unittest

from pages.weather_source import (
    LOCATIONS,
    Weather,
    WeatherService,
    WeatherSource,
    parse_weather,
    weather_label,
)


def immediate(target, args):
    class Thread:
        def start(self):
            target(*args)

    return Thread()


def payload():
    return {
        "current": {"temperature_2m": 12.5, "weather_code": 3},
        "daily": {
            "temperature_2m_max": [14.2],
            "temperature_2m_min": [8.1],
        },
    }


class ParseTests(unittest.TestCase):
    def test_fields_are_normalised(self):
        weather = parse_weather(payload(), "LONDON")
        self.assertEqual(weather.place, "LONDON")
        self.assertEqual(weather.temperature, 12.5)
        self.assertEqual(weather.code, 3)
        self.assertEqual(weather.high, 14.2)
        self.assertEqual(weather.low, 8.1)
        self.assertEqual(weather.condition, "OVERCAST")

    def test_missing_optional_fields(self):
        weather = parse_weather({"current": {}}, "PARIS")
        self.assertIsNone(weather.temperature)
        self.assertIsNone(weather.code)
        self.assertIsNone(weather.high)
        self.assertIsNone(weather.low)
        self.assertEqual(weather.condition, "UNKNOWN")

    def test_invalid_payload(self):
        with self.assertRaises(ValueError):
            parse_weather(None, "LONDON")
        with self.assertRaises(ValueError):
            parse_weather({}, "LONDON")

    def test_labels(self):
        self.assertEqual(weather_label(0), "CLEAR")
        self.assertEqual(weather_label(3), "OVERCAST")
        self.assertEqual(weather_label(95), "THUNDERSTORM")
        self.assertEqual(weather_label(None), "UNKNOWN")
        self.assertEqual(weather_label(999), "UNKNOWN")


class SourceTests(unittest.TestCase):
    def test_url_and_timeout(self):
        calls = []

        def fake_get_json(url, timeout=None):
            calls.append((url, timeout))
            return payload()

        source = WeatherSource(get_json=fake_get_json, timeout=2.0)
        weather = source.weather(LOCATIONS[0])
        self.assertEqual(weather.place, "LONDON")
        url, timeout = calls[0]
        self.assertIn("api.open-meteo.com", url)
        self.assertIn("latitude=51.5072", url)
        self.assertIn("longitude=-0.1276", url)
        self.assertIn("temperature_2m", url)
        self.assertEqual(timeout, 2.0)


class ServiceTests(unittest.TestCase):
    def test_snapshot_loads_for_a_location(self):
        class Source:
            def weather(self, location):
                return Weather(location.name, 10.0, 0, 12.0, 8.0)

        service = WeatherService(
            source=Source(), clock=lambda: 0.0, thread_factory=immediate
        )
        snapshot = service.weather(LOCATIONS[0])
        self.assertTrue(snapshot.loading)
        loaded = service.cache.snapshot("london")
        self.assertTrue(loaded.has_value)
        self.assertEqual(loaded.value.place, "LONDON")

    def test_start_prewarms_every_location(self):
        class Source:
            def weather(self, location):
                return Weather(location.name)

        service = WeatherService(
            source=Source(), clock=lambda: 0.0, thread_factory=immediate
        )
        asyncio.run(service.start())
        for location in service.locations:
            self.assertTrue(service.cache.snapshot(location.key).has_value)

    def test_failure_is_kept_as_an_error(self):
        class Source:
            def weather(self, location):
                raise RuntimeError("offline")

        service = WeatherService(
            source=Source(), clock=lambda: 0.0, thread_factory=immediate
        )
        service.weather(LOCATIONS[0])
        snapshot = service.cache.snapshot("london")
        self.assertFalse(snapshot.has_value)
        self.assertIsInstance(snapshot.error, RuntimeError)


if __name__ == "__main__":
    unittest.main()
