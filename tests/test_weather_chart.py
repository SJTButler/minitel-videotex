import time
import unittest

import pages

from minitel.data.cache import Snapshot
from minitel.session import Session
from minitel.terminal import profiles
from services.weather import LOCATIONS, DayForecast, Weather


def loaded(weather):
    return Snapshot(value=weather, loaded_at=time.monotonic())


def forecast():
    days = (
        DayForecast("2026-11-19", 14, 8, 0.0, 3),
        DayForecast("2026-11-20", 15, 9, 2.5, 61),
        DayForecast("2026-11-21", 13, 7, 4.0, 61),
        DayForecast("2026-11-22", 16, 10, 0.0, 2),
        DayForecast("2026-11-23", 17, 11, 0.0, 1),
        DayForecast("2026-11-24", 18, 12, 1.0, 3),
        DayForecast("2026-11-25", 19, 13, 0.0, 0),
    )
    return Weather("LONDON", 12, 3, 14, 8, days)


class FakeWeatherService:
    def __init__(self, snapshots):
        self.locations = LOCATIONS
        self.snapshots = snapshots

    def weather(self, location):
        return self.snapshots[location.key]


def make_session(services=None):
    registry = pages.build_registry()
    session = Session(
        registry,
        profiles.M1,
        initial=pages.INITIAL,
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
        services=services,
        header=pages.HEADER,
    )
    session.start()
    return session


def all_loaded(days=None):
    weather = forecast() if days is None else days
    return {
        location.key: loaded(
            Weather(
                location.name,
                weather.temperature,
                weather.code,
                weather.high,
                weather.low,
                weather.days,
            )
        )
        for location in LOCATIONS
    }


class WeatherChartTests(unittest.TestCase):
    def test_chart_page_draws_forecast(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("121")
        text = session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "WEATHER CHART")
        self.assertIn("LONDON", text[2])
        self.assertIn("7-DAY OUTLOOK", text[2])
        self.assertIn("HIGH", text[3])
        self.assertIn("LOW", text[3])
        self.assertIn("19C", text[4])
        self.assertEqual(text[4][5], "+")
        self.assertEqual(text[5][5], "|")
        self.assertIn("13C", text[8])
        self.assertEqual(text[8][5], "+")
        self.assertIn("7C", text[11])
        self.assertEqual(text[11][5], "+")
        self.assertEqual(text[14][:4].strip(), "4")
        self.assertEqual(text[14][5], "+")
        self.assertEqual(text[16][:4].strip(), "2")
        self.assertEqual(text[16][5], "+")
        self.assertEqual(text[18][:4].strip(), "0")
        self.assertEqual(text[18][5], "+")
        self.assertIn("PRECIPITATION MM", text[13])
        self.assertIn("UPDATED", text[19])
        self.assertIn("121#LON", text[21])
        self.assertIn("RETOUR=WEATHER", text[22])
        mosaic = [
            cell
            for row in session.screen.rows
            for cell in row
            if cell.mosaic is not None
        ]
        self.assertGreater(len(mosaic), 0)
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col),
            (20, 6),
        )

    def test_city_extension(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("121#PAR")
        text = session.screen.to_text().splitlines()
        self.assertIn("PAGE 121#PAR", text[0])
        self.assertIn("PARIS", text[2])
        self.assertIn("RETOUR=WEATHER", text[22])

    def test_unknown_city(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("121#XXX")
        text = session.screen.to_text()
        self.assertIn("NO CITY: XXX", text)
        self.assertIn("121#LON", text)
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col),
            (20, 6),
        )

    def test_loading(self):
        snapshots = {
            location.key: Snapshot(loading=True)
            for location in LOCATIONS
        }
        session = make_session({"weather": FakeWeatherService(snapshots)})
        session.navigate("121")
        text = session.screen.to_text()
        self.assertIn("LOADING WEATHER...", text)

    def test_unavailable(self):
        snapshots = {
            location.key: Snapshot(error=RuntimeError("offline"))
            for location in LOCATIONS
        }
        session = make_session({"weather": FakeWeatherService(snapshots)})
        session.navigate("121")
        text = session.screen.to_text()
        self.assertIn("NO FORECAST", text)
        self.assertIn("UNAVAILABLE", text)

    def test_missing_service(self):
        session = make_session()
        session.navigate("121")
        text = session.screen.to_text()
        self.assertIn("WEATHER SERVICE NOT CONFIGURED", text)
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col),
            (20, 6),
        )

    def test_no_days(self):
        weather = Weather("LONDON", 12, 3, 14, 8, ())
        session = make_session({"weather": FakeWeatherService(all_loaded(weather))})
        session.navigate("121")
        self.assertIn("NO FORECAST DATA", session.screen.to_text())

    def test_weather_page_links_to_the_chart(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("120")
        self.assertIn("CHART: 121#LON", session.screen.to_text())
        session.navigate("120#PAR")
        self.assertIn("CHART: 121#PAR", session.screen.to_text())


if __name__ == "__main__":
    unittest.main()
