import unittest

from minitel.data.http import HttpError

from services.train.models import DepartureBoard
from services.train.source import RttSource
from services.train.service import TrainService

BASE = "https://data.rtt.io"


def _departure(
    *,
    when="2026-11-15T12:34:00Z",
    expected=None,
    lateness=None,
    cancelled=False,
    display="CALL",
    platform="4",
    destination="BIRMINGHAM INTERNATIONAL",
):
    departure = {"scheduleAdvertised": when}
    if expected:
        departure["realtimeForecast"] = expected
    if lateness is not None:
        departure["realtimeAdvertisedLateness"] = lateness
    if cancelled:
        departure["isCancelled"] = True
    return {
        "scheduleMetadata": {
            "uniqueIdentity": "gb-nr:L1:2026-11-15",
            "operator": {"code": "XC", "name": "CrossCountry"},
        },
        "temporalData": {
            "departure": departure,
            "displayAs": display,
        },
        "locationMetadata": {
            "platform": {"planned": "1", "actual": platform},
        },
        "destination": [
            {
                "location": {
                    "description": destination,
                    "shortCodes": ["BHM"],
                }
            }
        ],
    }


def _payload(*services, realtime="OK", core="OK"):
    return {
        "systemStatus": {
            "realtimeNetworkRail": realtime,
            "rttCore": core,
        },
        "query": {"location": {"description": "London Paddington"}},
        "services": list(services),
    }


class FakeJson:
    def __init__(self, payloads, reference=None):
        self.payloads = list(payloads)
        self.reference = reference or {"locations": []}
        self.calls = []

    def __call__(self, url, headers=None, timeout=10.0):
        self.calls.append((url, dict(headers or {})))
        if url.endswith("/api/get_access_token"):
            return {
                "token": "ACCESS",
                "validUntil": "2030-01-01T00:00:00Z",
            }
        if url.endswith("/data/locations_ungrouped"):
            return self.reference
        result = self.payloads.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class RttSourceTests(unittest.TestCase):
    def test_refresh_token_is_exchanged_and_used(self):
        fake = FakeJson([_payload(_departure(lateness=2))])
        source = RttSource(
            refresh_token="REFRESH",
            get_json=fake,
            clock=lambda: 1000.0,
        )

        board = source.departures("PAD", "BHM")

        self.assertEqual(board.station, "London Paddington")
        self.assertEqual(board.filter_to, "BHM")
        self.assertEqual(len(board.departures), 1)
        departure = board.departures[0]
        self.assertEqual(departure.scheduled, "12:34")
        self.assertEqual(departure.destination, "BIRMINGHAM INTERNATIONAL")
        self.assertEqual(departure.platform, "4")
        self.assertEqual(departure.operator, "CrossCountry")
        self.assertEqual(departure.status, "+2")
        self.assertIn("/api/get_access_token", fake.calls[0][0])
        self.assertEqual(
            fake.calls[0][1]["Authorization"], "Bearer REFRESH"
        )
        self.assertIn("code=PAD", fake.calls[1][0])
        self.assertIn("filterTo=BHM", fake.calls[1][0])
        self.assertEqual(
            fake.calls[1][1]["Authorization"], "Bearer ACCESS"
        )

    def test_long_life_access_token_skips_the_exchange(self):
        fake = FakeJson([_payload(_departure())])
        source = RttSource(access_token="LONG", get_json=fake)

        board = source.departures("PAD")

        self.assertTrue(board.departures)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(
            fake.calls[0][1]["Authorization"], "Bearer LONG"
        )

    def test_204_is_an_empty_board(self):
        fake = FakeJson([HttpError(f"{BASE}/gb-nr/location", status=204)])
        source = RttSource(access_token="LONG", get_json=fake)

        board = source.departures("PAD")

        self.assertIsInstance(board, DepartureBoard)
        self.assertEqual(board.departures, ())

    def test_401_refreshes_once_and_retries(self):
        fake = FakeJson([
            HttpError(f"{BASE}/gb-nr/location", status=401),
            _payload(_departure()),
        ])
        source = RttSource(
            refresh_token="REFRESH",
            get_json=fake,
            clock=lambda: 1000.0,
        )

        board = source.departures("PAD")

        self.assertTrue(board.departures)
        self.assertEqual(sum(
            1 for url, _ in fake.calls if url.endswith("/get_access_token")
        ), 2)

    def test_pass_and_terminating_services_are_filtered(self):
        fake = FakeJson([_payload(
            _departure(display="PASS"),
            _departure(display="TERMINATES"),
            _departure(display="CALL"),
        )])
        source = RttSource(access_token="LONG", get_json=fake)

        board = source.departures("PAD")

        self.assertEqual(len(board.departures), 1)

    def test_cancellation_uses_the_cancel_status(self):
        fake = FakeJson([_payload(
            _departure(cancelled=True, display="CANCELLED")
        )])
        source = RttSource(access_token="LONG", get_json=fake)

        departure = source.departures("PAD").departures[0]

        self.assertTrue(departure.cancelled)
        self.assertEqual(departure.status, "CANCEL")

    def test_summer_times_are_london_local(self):
        fake = FakeJson([_payload(
            _departure(when="2026-07-01T12:00:00Z")
        )])
        source = RttSource(access_token="LONG", get_json=fake)

        departure = source.departures("PAD").departures[0]

        self.assertEqual(departure.scheduled, "13:00")

    def test_degraded_system_status_is_exposed(self):
        fake = FakeJson([_payload(
            _departure(), realtime="REALTIME_DATA_LIMITED",
            core="SCHEDULE_ONLY",
        )])
        source = RttSource(access_token="LONG", get_json=fake)

        board = source.departures("PAD")

        self.assertIn("REALTIME LIMITED", board.degraded)
        self.assertIn("SCHEDULE ONLY", board.degraded)

    def test_station_names_are_resolved_from_reference_data(self):
        fake = FakeJson([], reference={
            "locations": [
                {"shortCode": "WAT", "description": "London Waterloo"},
                {"shortCode": "HXX", "description": "Heathrow Terminals 2 & 3"},
            ]
        })
        source = RttSource(access_token="LONG", get_json=fake)

        source._load_names()

        self.assertEqual(source.station_name("HXX"), "Heathrow Terminals 2 & 3")
        self.assertEqual(source.station_name("WAT"), "London Waterloo")
        self.assertEqual(
            sum(1 for url, _ in fake.calls
                if url.endswith("/data/locations_ungrouped")),
            1,
        )

    def test_missing_token_is_not_configured(self):
        source = RttSource(get_json=FakeJson([]))

        self.assertFalse(source.configured)
        with self.assertRaises(RuntimeError):
            source.departures("PAD")

    def test_train_service_exposes_configured(self):
        source = RttSource(access_token="LONG", get_json=FakeJson([
            _payload(_departure())
        ]))
        service = TrainService(source)

        self.assertTrue(service.configured)
        snapshot = service.departures("PAD")
        self.assertIsNotNone(snapshot)


if __name__ == "__main__":
    unittest.main()
