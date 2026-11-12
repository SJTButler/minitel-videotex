import time
import unittest

import pages

from minitel.terminal import profiles
from minitel.data.cache import Snapshot
from minitel.session import Session
from services.weather import LOCATIONS, Weather

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])


def loaded(weather, when=None):
    return Snapshot(
        value=weather,
        loaded_at=time.monotonic() if when is None else when,
    )


def all_loaded():
    return {
        "london": loaded(Weather("LONDON", 12.6, 2, 14.2, 8.1)),
        "paris": loaded(Weather("PARIS", 15.2, 0, 18.0, 10.4)),
        "lyon": loaded(Weather("LYON", 11.8, 61, 14.0, 7.2)),
        "marseille": loaded(Weather("MARSEILLE", 18.4, 1, 21.0, 13.1)),
    }


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


class WeatherPageTests(unittest.TestCase):
    def test_lists_cities_and_forecasts(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("120")
        text = session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "WEATHER")
        self.assertEqual(text[2].strip(), "CURRENT CONDITIONS")
        self.assertIn("LONDON", text[5])
        self.assertIn("13C", text[5])
        self.assertIn("PARTLY CLOUDY", text[5])
        self.assertIn("8/14", text[5])
        self.assertEqual(text[12].strip(), "SOURCE: OPEN-METEO")
        self.assertIn("UPDATED", text[13])
        self.assertIn("120#LON", text[14])
        self.assertIn("120#PAR", text[14])

    def test_loading_state(self):
        snapshots = {
            location.key: Snapshot(loading=True)
            for location in LOCATIONS
        }
        session = make_session({"weather": FakeWeatherService(snapshots)})
        session.navigate("120")
        text = session.screen.to_text()
        self.assertIn("LOADING WEATHER...", text)
        self.assertIn("LOADING...", text)

    def test_unavailable_state(self):
        snapshots = {
            location.key: Snapshot(error=RuntimeError("offline"))
            for location in LOCATIONS
        }
        session = make_session({"weather": FakeWeatherService(snapshots)})
        session.navigate("120")
        text = session.screen.to_text()
        self.assertIn("WEATHER UNAVAILABLE", text)
        self.assertIn("NO DATA", text)

    def test_offline_cached_state(self):
        snapshots = all_loaded()
        snapshots["london"] = Snapshot(
            value=Weather("LONDON", 12.6, 3, 14.2, 8.1),
            loaded_at=time.monotonic(),
            error=RuntimeError("offline"),
        )
        session = make_session({"weather": FakeWeatherService(snapshots)})
        session.navigate("120")
        text = session.screen.to_text()
        self.assertIn("OFFLINE - CACHED", text)
        self.assertIn("LONDON", text)

    def test_missing_service(self):
        session = make_session()
        session.navigate("120")
        text = session.screen.to_text()
        self.assertIn("WEATHER SERVICE NOT CONFIGURED", text)
        self.assertIn("WEATHER NOT CONFIGURED", text)

    def test_missing_values_render_as_dashes(self):
        snapshots = {
            location.key: loaded(Weather(location.name))
            for location in LOCATIONS
        }
        session = make_session({"weather": FakeWeatherService(snapshots)})
        session.navigate("120")
        row = session.screen.to_text().splitlines()[5]
        self.assertIn("--", row)
        self.assertIn("UNKNOWN", row)

    def test_tick_picks_up_a_background_load(self):
        snapshots = {
            location.key: Snapshot(loading=True)
            for location in LOCATIONS
        }
        service = FakeWeatherService(snapshots)
        session = make_session({"weather": service})
        session.navigate("120")
        self.assertIn("LOADING WEATHER...", session.screen.to_text())

        service.snapshots = all_loaded()
        session.tick()
        self.assertIn("UPDATED", session.screen.to_text())

    def test_page_has_input_and_footer(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("120")
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col),
            (20, 6),
        )
        self.assertTrue(
            session.screen.to_text().splitlines()[22].startswith("SOMMAIRE=HOME")
        )

    def test_location_codes_are_short_and_unique(self):
        codes = [location.code for location in LOCATIONS]
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            self.assertTrue(code.isascii())
            self.assertTrue(code.isalnum())
            self.assertEqual(code, code.upper())
            self.assertLessEqual(len(code), 6)

    def test_city_detail_from_extension(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("120#PAR")

        self.assertEqual(session.current.number, "120#PAR")
        text = session.screen.to_text().splitlines()
        self.assertIn("PAGE 120#PAR", text[0])
        self.assertEqual(text[2].strip(), "CITY DETAIL")
        self.assertIn("PARIS", text[4])
        self.assertIn("15C", text[6])
        self.assertIn("CLEAR", text[7])
        self.assertIn("10/18", text[8])
        self.assertIn("SOURCE: OPEN-METEO", text[11])
        self.assertIn("UPDATED", text[13])
        self.assertIn("RETOUR=WEATHER", text[22])
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col),
            (20, 6),
        )

    def test_direct_city_retour_goes_to_weather_then_home(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("120#PAR")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "120")
        self.assertIn("CURRENT CONDITIONS", session.screen.to_text())

        session.feed(RETOUR)
        self.assertEqual(session.current.number, pages.INITIAL)

    def test_city_entered_from_weather_retour_returns_to_weather(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("120")
        session.navigate("120#PAR")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "120")

    def test_invalid_city_message_and_recovery(self):
        session = make_session({"weather": FakeWeatherService(all_loaded())})
        session.navigate("120#ZZZ")

        self.assertEqual(session.current.number, "120#ZZZ")
        text = session.screen.to_text()
        self.assertIn("NO CITY: ZZZ", text)
        self.assertIn("120#PAR", text)

        session.feed(b"120#PAR" + ENVOI)
        self.assertEqual(session.current.number, "120#PAR")
        self.assertIn("PARIS", session.screen.to_text())

    def test_detail_tick_updates(self):
        snapshots = {
            location.key: Snapshot(loading=True)
            for location in LOCATIONS
        }
        service = FakeWeatherService(snapshots)
        session = make_session({"weather": service})
        session.navigate("120#PAR")
        self.assertIn("LOADING...", session.screen.to_text())

        service.snapshots = all_loaded()
        session.tick()
        self.assertIn("PARIS", session.screen.to_text())
        self.assertIn("15C", session.screen.to_text())

    def test_detail_missing_service(self):
        session = make_session()
        session.navigate("120#PAR")
        text = session.screen.to_text()
        self.assertIn("WEATHER SERVICE NOT CONFIGURED", text)
        self.assertIn("RETOUR=WEATHER", text)

    def test_detail_error(self):
        snapshots = {
            location.key: Snapshot(error=RuntimeError("offline"))
            for location in LOCATIONS
        }
        session = make_session({"weather": FakeWeatherService(snapshots)})
        session.navigate("120#PAR")
        text = session.screen.to_text()
        self.assertIn("NO DATA", text)
        self.assertIn("WEATHER UNAVAILABLE", text)


if __name__ == "__main__":
    unittest.main()
