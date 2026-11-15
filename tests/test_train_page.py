import time
import unittest

import pages

from minitel import M1, Session
from minitel.data.cache import Snapshot

from services.train.models import Departure, DepartureBoard

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SUITE = bytes([0x13, 0x48])


def _departure(index, *, status="ON TIME"):
    return Departure(
        scheduled=f"{12 + index // 60:02d}:{index % 60:02d}",
        expected=None,
        destination=f"DEST {index}",
        platform=str(index % 9 + 1),
        operator="TEST RAIL",
        status=status,
        cancelled=status == "CANCEL",
        unique_identity=f"gb-nr:T{index}:2026-11-15",
    )


def _board(count=3, degraded=None, station="LONDON PADDINGTON"):
    return DepartureBoard(
        station=station,
        filter_to=None,
        departures=tuple(_departure(index) for index in range(count)),
        degraded=degraded,
    )


def _snapshot(value=None, *, error=None):
    return Snapshot(
        value=value,
        loaded_at=time.monotonic() if value is not None else None,
        error=error,
    )


class FakeTrainService:
    def __init__(self, snapshot=None, *, configured=True):
        self.snapshot = snapshot if snapshot is not None else _snapshot()
        self.configured = configured
        self.calls = []

    def departures(self, origin, destination=None):
        self.calls.append((origin, destination))
        return self.snapshot

    def station_name(self, code):
        return {"HXX": "Heathrow Terminals 2 & 3", "WOK": "Woking"}.get(code)


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
    session.navigate("170")
    return session


class TrainPageTests(unittest.TestCase):
    def test_page_is_registered_with_alias_and_service(self):
        registry = pages.build_registry()
        page = registry.get("170")
        self.assertEqual(page.title, "TRAIN TIMES")
        self.assertIn("7", registry.aliases_for(page))
        self.assertEqual(page.requires, ("train",))
        self.assertTrue(page.form)
        self.assertFalse(page.scroll)
        self.assertTrue(page.extensions)
        self.assertEqual(page.extension_back_page, "100")
        self.assertIs(registry.get("7"), page)

    def test_initial_render_prompts_for_a_station(self):
        service = FakeTrainService()
        session = make_session(service)

        self.assertEqual(session.focused_region, "form")
        text = session.screen.to_text()
        self.assertIn("TYPE A FROM CODE", text)
        self.assertIn("SOURCE: REALTIME TRAINS", text)
        form = text.splitlines()[2]
        self.assertTrue(form.startswith("FROM:"))
        self.assertIn("TO:", form)
        self.assertEqual(service.calls, [])

    def test_submit_loads_departures_and_focuses_results(self):
        service = FakeTrainService(_snapshot(_board(3)))
        session = make_session(service)

        session.feed(b"PAD" + ENVOI)

        self.assertEqual(service.calls, [("PAD", "")])
        self.assertEqual(session.focused_region, "results")
        self.assertEqual(session.state["train_query"], ("PAD", ""))
        text = session.screen.to_text()
        self.assertIn("LONDON PADDINGTON", text)
        self.assertIn("DEST 0", text)
        self.assertIn("1/1", text)

    def test_table_columns_line_up(self):
        service = FakeTrainService(_snapshot(_board(3)))
        session = make_session(service)
        session.feed(b"PAD" + ENVOI)
        lines = session.screen.to_text().splitlines()

        self.assertEqual(lines[5].index("DESTINATION"), 6)
        self.assertEqual(lines[5].index("PLT"), 28)
        self.assertEqual(lines[5].index("STATUS"), 32)
        self.assertEqual(lines[6].index("DEST 0"), 6)

    def test_destination_name_is_resolved(self):
        service = FakeTrainService(
            _snapshot(_board(0, station="LONDON WATERLOO"))
        )
        session = make_session(service)

        session.feed(b"WAT" + SUITE + b"HXX" + ENVOI)

        text = session.screen.to_text()
        self.assertIn("LONDON WATERLOO TO Heathrow", text)
        self.assertIn("NO DIRECT TO HXX", text)

    def test_direct_only_filter_has_a_clear_empty_state(self):
        service = FakeTrainService(_snapshot(_board(0)))
        session = make_session(service)

        session.feed(b"WAT" + SUITE + b"HXX" + ENVOI)

        text = session.screen.to_text()
        self.assertIn("NO DIRECT TO HXX", text)
        self.assertIn("DIRECT SERVICES ONLY", text)

    def test_direct_route_prefills_and_loads(self):
        service = FakeTrainService(
            _snapshot(_board(0, station="LONDON WATERLOO"))
        )
        session = make_session(service)

        session.navigate("170#WATHXX")

        self.assertEqual(session.current.number, "170#WATHXX")
        self.assertEqual(session.focused_region, "results")
        self.assertEqual(session.values["origin"], "WAT")
        self.assertEqual(session.values["destination"], "HXX")
        self.assertEqual(service.calls, [("WAT", "HXX")])
        text = session.screen.to_text()
        self.assertIn("LONDON WATERLOO TO Heathrow", text)
        self.assertIn("NO DIRECT TO HXX", text)

    def test_direct_route_can_be_origin_only(self):
        service = FakeTrainService(_snapshot(_board(0)))
        session = make_session(service)

        session.navigate("170#WAT")

        self.assertEqual(session.values["origin"], "WAT")
        self.assertEqual(session.values["destination"], "")
        self.assertEqual(service.calls, [("WAT", "")])

    def test_bad_route_returns_to_the_form_with_an_error(self):
        service = FakeTrainService()
        session = make_session(service)

        session.navigate("170#AB")

        self.assertEqual(session.focused_region, "form")
        self.assertIn("USE 170#FROMTO", session.screen.to_text())
        self.assertEqual(service.calls, [])

    def test_extension_retour_follows_history(self):
        service = FakeTrainService(_snapshot(_board(0)))
        session = make_session(service)
        session.navigate("100")
        session.navigate("170#WATHXX")

        session.feed(RETOUR)  # first results page -> form
        session.feed(RETOUR)  # form root -> history

        self.assertEqual(session.current.number, "100")

    def test_pager_pages_and_retour_returns_to_the_form(self):
        service = FakeTrainService(_snapshot(_board(10)))
        session = make_session(service)
        session.feed(b"PAD" + ENVOI)

        session.feed(SUITE)
        self.assertEqual(
            session.regions["results"].cursor.page_number, 2
        )
        self.assertIn("DEST 8", session.screen.to_text())

        session.feed(RETOUR)
        self.assertEqual(
            session.regions["results"].cursor.page_number, 1
        )
        session.feed(RETOUR)
        self.assertEqual(session.focused_region, "form")

    def test_returning_restores_the_form_from_the_query(self):
        service = FakeTrainService(_snapshot(_board(1)))
        session = make_session(service)
        session.feed(b"PAD" + ENVOI)
        session.navigate("100")
        session.navigate("170")

        self.assertEqual(session.focused_region, "results")
        self.assertEqual(session.values["origin"], "PAD")
        self.assertIn("FROM: PAD", session.screen.to_text())

    def test_root_retour_goes_home(self):
        service = FakeTrainService(_snapshot(_board(3)))
        session = make_session(service)
        session.feed(b"PAD" + ENVOI)
        session.feed(RETOUR)
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "100")

    def test_invalid_origin_keeps_focus_on_the_form(self):
        service = FakeTrainService()
        session = make_session(service)

        session.feed(b"P" + ENVOI)

        self.assertEqual(session.focused_region, "form")
        self.assertEqual(session.active_name, "origin")
        self.assertIn("USE 3-LETTER CRS CODES", session.screen.to_text())
        self.assertEqual(service.calls, [])

    def test_destination_is_optional_but_validated(self):
        service = FakeTrainService(_snapshot(_board(1)))
        session = make_session(service)

        session.feed(b"PAD" + SUITE + b"K" + ENVOI)

        self.assertEqual(session.focused_region, "form")
        self.assertEqual(session.active_name, "destination")
        self.assertIn("USE 3-LETTER CRS CODES", session.screen.to_text())
        self.assertEqual(service.calls, [])

    def test_not_configured_does_not_call_the_source(self):
        service = FakeTrainService(configured=False)
        session = make_session(service)

        session.feed(b"PAD" + ENVOI)

        self.assertEqual(service.calls, [])
        self.assertIn("TRAIN DATA NOT CONFIGURED", session.screen.to_text())

    def test_unavailable_and_empty_states(self):
        unavailable = FakeTrainService(
            _snapshot(error=RuntimeError("offline"))
        )
        session = make_session(unavailable)
        session.feed(b"PAD" + ENVOI)
        self.assertIn("TRAIN DATA UNAVAILABLE", session.screen.to_text())

        empty = FakeTrainService(_snapshot(_board(0)))
        session = make_session(empty)
        session.feed(b"PAD" + ENVOI)
        self.assertIn("NO DEPARTURES", session.screen.to_text())

    def test_stale_data_is_labelled(self):
        stale = _snapshot(_board(1), error=RuntimeError("offline"))
        service = FakeTrainService(stale)
        session = make_session(service)

        session.feed(b"PAD" + ENVOI)

        self.assertIn("OFFLINE - CACHED", session.screen.to_text())
        self.assertIn("DEST 0", session.screen.to_text())

    def test_enter_on_results_refreshes_without_resubmitting(self):
        service = FakeTrainService(_snapshot(_board(1)))
        session = make_session(service)
        session.feed(b"PAD" + ENVOI)
        self.assertEqual(len(service.calls), 1)

        session.feed(ENVOI)

        self.assertEqual(len(service.calls), 2)
        self.assertEqual(session.focused_region, "results")

    def test_tick_keeps_focus_and_page(self):
        service = FakeTrainService(_snapshot(_board(10)))
        session = make_session(service)
        session.feed(b"PAD" + ENVOI)
        session.feed(SUITE)

        session.tick()

        self.assertIsNone(session.page_error)
        self.assertEqual(session.focused_region, "results")
        self.assertEqual(
            session.regions["results"].cursor.page_number, 2
        )


if __name__ == "__main__":
    unittest.main()
