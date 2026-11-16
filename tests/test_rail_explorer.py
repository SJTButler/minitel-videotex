import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pages

from minitel import M1, Session
from minitel.data.cache import Snapshot

from services.train.models import (
    Departure,
    DepartureBoard,
    ServiceDetail,
    ServiceStop,
)

LONDON = ZoneInfo("Europe/London")


def _scheduled_at(scheduled, day="2026-11-15"):
    hour, minute = (int(part) for part in scheduled.split(":"))
    year, month, date = (int(part) for part in day.split("-"))
    return datetime(year, month, date, hour, minute, tzinfo=LONDON)


ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])


def _departure(uid, scheduled, destination, platform="1", day="2026-11-15"):
    return Departure(
        scheduled=scheduled,
        expected=None,
        destination=destination,
        platform=platform,
        operator="TEST RAIL",
        status="ON TIME",
        cancelled=False,
        unique_identity=uid,
        scheduled_at=_scheduled_at(scheduled, day),
    )


def _board(station, *departures):
    return DepartureBoard(station, None, tuple(departures))


def _detail(uid, *stops, day="2026-11-15"):
    return ServiceDetail(uid, tuple(
        ServiceStop(
            code, name, scheduled, arrival,
            _scheduled_at(arrival, day),
            platform, cancelled,
        )
        for code, name, scheduled, arrival, platform, cancelled in stops
    ))


FTN_DEPARTURES = _board(
    "FRATTON",
    _departure("gb-nr:T1:2026-11-15", "17:22", "HAVANT"),
    _departure("gb-nr:T2:2026-11-15", "17:40", "BRIGHTON"),
)
HAV_DEPARTURES = _board(
    "HAVANT",
    _departure("gb-nr:T1:2026-11-15", "17:30", "BRIGHTON", "1"),
    _departure("gb-nr:T4:2026-11-15", "17:20", "EARLY", "1"),
    _departure("gb-nr:T3:2026-11-15", "17:35", "ANGMERING", "2"),
)
ANG_DEPARTURES = _board("ANGMERING")

TRAIN_1 = _detail(
    "gb-nr:T1:2026-11-15",
    ("FTN", "Fratton", "17:22", "17:22", "1", False),
    ("HAV", "Havant", "17:28", "17:28", "1", False),
    ("ANG", "Angmering", "17:41", "17:41", "2", False),
)
TRAIN_3 = _detail(
    "gb-nr:T3:2026-11-15",
    ("HAV", "Havant", "17:35", "17:35", "2", False),
    ("ANG", "Angmering", "17:48", "17:48", "2", False),
)


class FakeTrainService:
    configured = True

    def __init__(self):
        self.departure_calls = []
        self.time_from_calls = []
        self.service_calls = []

    def departures(self, origin, destination=None, *, time_from=None):
        self.departure_calls.append((origin, destination))
        self.time_from_calls.append(time_from)
        boards = {
            "FTN": FTN_DEPARTURES,
            "HAV": HAV_DEPARTURES,
            "ANG": ANG_DEPARTURES,
        }
        value = boards.get(origin, DepartureBoard(origin, destination, ()))
        if time_from is not None:
            value = DepartureBoard(
                value.station,
                value.filter_to,
                tuple(
                    departure for departure in value.departures
                    if departure.scheduled_at is None
                    or departure.scheduled_at >= time_from
                ),
                value.degraded,
            )
        return Snapshot(value=value, loaded_at=time.monotonic())

    def service(self, uid):
        self.service_calls.append(uid)
        details = {
            "gb-nr:T1:2026-11-15": TRAIN_1,
            "gb-nr:T3:2026-11-15": TRAIN_3,
        }
        return Snapshot(
            value=details.get(uid),
            loaded_at=time.monotonic(),
        )


def make_session(service):
    registry = pages.build_registry()
    session = Session(
        registry,
        M1,
        initial="100",
        fallback=registry.get("100"),
        services={"train": service},
    )
    session.start()
    return session


class MidnightService(FakeTrainService):
    def departures(self, origin, destination=None, *, time_from=None):
        self.departure_calls.append((origin, destination))
        self.time_from_calls.append(time_from)
        if origin == "FTN":
            board = _board(
                "FRATTON",
                _departure(
                    "gb-nr:M1:2026-11-16", "00:02",
                    "PORTSMOUTH HARBOUR", day="2026-11-16",
                ),
            )
        elif origin == "BAA":
            board = _board(
                "BARNHAM",
                _departure(
                    "gb-nr:E1:2026-11-15", "22:17",
                    "LONDON VICTORIA", day="2026-11-15",
                ),
                _departure(
                    "gb-nr:E2:2026-11-15", "23:01",
                    "BRIGHTON", day="2026-11-15",
                ),
                _departure(
                    "gb-nr:M2:2026-11-16", "00:43",
                    "LITTLEHAMPTON", day="2026-11-16",
                ),
            )
        else:
            board = DepartureBoard(origin, destination, ())
        if time_from is not None:
            board = DepartureBoard(
                board.station,
                board.filter_to,
                tuple(
                    departure for departure in board.departures
                    if departure.scheduled_at is None
                    or departure.scheduled_at >= time_from
                ),
                board.degraded,
            )
        return Snapshot(value=board, loaded_at=time.monotonic())

    def service(self, uid):
        self.service_calls.append(uid)
        detail = _detail(
            uid,
            ("FTN", "Fratton", "00:02", "00:02", "1", False),
            ("BAA", "Barnham", "00:18", "00:20", "2", False),
            day="2026-11-16",
        )
        return Snapshot(value=detail, loaded_at=time.monotonic())


class RailExplorerTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeTrainService()
        self.session = make_session(self.service)
        self.session.navigate("171#FTN")

    def test_page_metadata(self):
        registry = pages.build_registry()
        page = registry.get("171")
        self.assertEqual(page.title, "RAIL EXPLORER")
        self.assertTrue(page.extensions)
        self.assertEqual(page.back_page, "170")
        self.assertEqual(page.extension_back_page, "170")
        self.assertEqual(registry.get("171#FTN").number, "171#FTN")

    def test_pick_phase_lists_trains(self):
        self.assertEqual(self.session.current.number, "171#FTN")
        self.assertEqual(self.session.state["rail_phase"], "pick")
        text = self.session.screen.to_text()
        self.assertIn("PICK A TRAIN FROM FTN", text)
        self.assertIn("HAVANT", text)
        self.assertEqual(self.service.departure_calls, [("FTN", "")])
        self.assertEqual(self.session.focused_region, "calls")

    def test_pick_commit_switches_to_calls_and_clears_right(self):
        self.session.feed(ENVOI)
        self.assertEqual(self.session.state["rail_phase"], "explore")
        self.assertEqual(self.session.state["rail_base"], "FTN")
        self.assertEqual(self.session.state["rail_alight"], None)
        self.assertEqual(self.session.state["rail_path"], ["FTN"])
        self.assertEqual(self.session.focused_region, "calls")
        text = self.session.screen.to_text()
        self.assertIn("CALLS", text)
        self.assertIn("NO STATION", text)
        self.assertIn("Havant", text)

    def test_left_commit_loads_station_departures(self):
        self.session.feed(ENVOI)  # take train T1
        self.session.feed(ENVOI)  # commit HAVANT

        self.assertEqual(self.session.state["rail_alight"], "HAV")
        self.assertEqual(self.session.state["rail_path"], ["FTN", "HAV"])
        self.assertEqual(self.session.focused_region, "trains")
        self.assertIn(("HAV", None), self.service.departure_calls)
        text = self.session.screen.to_text()
        self.assertIn("FROM HAV 17:28+", text)
        self.assertEqual(
            self.service.time_from_calls[-1],
            datetime(2026, 11, 15, 17, 28, tzinfo=LONDON),
        )
        self.assertIn("ANGMERING", text)
        self.assertNotIn("EARLY", text)
        self.assertNotIn("BRIGHTON", text)
        self.assertIn("PATH FTN > HAV  0:06", text)

    def test_right_commit_updates_calls_and_clears_right(self):
        self.session.feed(ENVOI)
        self.session.feed(ENVOI)
        self.session.feed(ENVOI)  # take T3 at HAVANT

        self.assertEqual(self.session.state["rail_base"], "HAV")
        self.assertEqual(self.session.state["rail_alight"], None)
        self.assertEqual(self.session.state["rail_path"], ["FTN", "HAV"])
        self.assertEqual(self.session.focused_region, "calls")
        text = self.session.screen.to_text()
        self.assertIn("NO STATION", text)
        self.assertIn("Angmering", text)

        self.session.feed(ENVOI)  # commit ANG
        self.assertEqual(
            self.session.state["rail_path"], ["FTN", "HAV", "ANG"]
        )
        self.assertIn(
            "PATH FTN > HAV > ANG  0:26",
            self.session.screen.to_text(),
        )

    def test_suite_does_not_fetch_the_other_pane(self):
        self.session.feed(ENVOI)
        calls_before = len(self.service.departure_calls)
        self.session.feed(SUITE)
        self.assertEqual(
            len(self.service.departure_calls), calls_before
        )

    def test_tick_preserves_focus_and_selection(self):
        self.session.feed(ENVOI)
        selected = self.session.regions["calls"].cursor.selected
        self.session.tick()
        self.assertIsNone(self.session.page_error)
        self.assertEqual(self.session.focused_region, "calls")
        self.assertEqual(
            self.session.regions["calls"].cursor.selected, selected
        )

    def test_midnight_connection_queries_after_arrival(self):
        service = MidnightService()
        session = make_session(service)
        session.navigate("171#FTNBAA")
        session.feed(ENVOI)  # pick the 00:02 train
        session.feed(ENVOI)  # commit Barnham

        self.assertEqual(
            service.time_from_calls[-1],
            datetime(2026, 11, 16, 0, 20, tzinfo=LONDON),
        )
        text = session.screen.to_text()
        self.assertIn("FROM BAA 00:20+", text)
        self.assertIn("LITTLEHAMPT", text)
        self.assertNotIn("LONDON VICTORIA", text)
        self.assertNotIn("BRIGHTON", text)
        self.assertIn("PATH FTN > BAA  0:18", text)

    def test_back_stack_walks_the_pane_states(self):
        self.session.feed(ENVOI)  # A -> B
        self.session.feed(ENVOI)  # B -> C
        self.session.feed(ENVOI)  # C -> D

        self.assertEqual(self.session.state["rail_path"], ["FTN", "HAV"])
        self.assertEqual(self.session.state["rail_alight"], None)

        self.session.feed(RETOUR)  # D -> C
        self.assertEqual(self.session.focused_region, "trains")
        self.assertEqual(self.session.state["rail_alight"], "HAV")
        self.assertIn("Angmering", self.session.screen.to_text())

        self.session.feed(RETOUR)  # C -> B
        self.assertEqual(self.session.focused_region, "calls")
        self.assertEqual(self.session.state["rail_alight"], None)
        self.assertIn("NO STATION", self.session.screen.to_text())

        self.session.feed(RETOUR)  # B -> A
        self.assertEqual(self.session.state["rail_phase"], "pick")
        self.assertIn(
            "PICK A TRAIN FROM FTN", self.session.screen.to_text()
        )

    def test_empty_stack_falls_back_to_170(self):
        self.session.feed(RETOUR)
        self.assertEqual(self.session.current.number, "170")

    def test_filtered_entry(self):
        session = make_session(FakeTrainService())
        session.navigate("171#FTNHAV")

        self.assertEqual(session.state["rail_filter"], "HAV")
        self.assertEqual(
            session.registry.get("171#FTNHAV").extension, "FTNHAV"
        )

    def test_bare_and_invalid_entry(self):
        session = make_session(FakeTrainService())
        session.navigate("171")
        self.assertIn("USE 171#FROM", session.screen.to_text())

        session.navigate("171#AB")
        self.assertIn("USE 171#FROM", session.screen.to_text())
        self.assertEqual(session.focused_region, "calls")

    def test_explore_columns_line_up(self):
        self.session.feed(ENVOI)
        self.session.feed(ENVOI)
        lines = self.session.screen.to_text().splitlines()

        self.assertEqual(lines[5].index("TIME"), 0)
        self.assertEqual(lines[5].index("TIME", 1), 19)
        self.assertEqual(lines[5].index("STATION"), 6)
        self.assertEqual(lines[5].index("DESTINATION"), 25)
        self.assertEqual(lines[6].index("Havant"), 6)
        self.assertEqual(lines[6].index("ANGMERING"), 25)


if __name__ == "__main__":
    unittest.main()
