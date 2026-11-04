import time
import unittest
from datetime import datetime, timezone

import pages

from minitel.protocol import codec
from minitel.terminal import profiles
from minitel.data.cache import Snapshot
from minitel.session import Session
from pages.sports._support.labels import competition_label
from pages.sports._support.layout import kickoff_label
from services.sports.config import SportsConfig
from services.sports.models import (
    Alert,
    FeedSnapshot,
    Match,
    MatchStatus,
    StandingRow,
    Team,
)

ENVOI = bytes([0x13, 0x41])
RETOUR = bytes([0x13, 0x42])
SOMMAIRE = bytes([0x13, 0x46])
SUITE = bytes([0x13, 0x48])

KICKOFF = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)


def loaded_snapshot(matches, alerts=(), error=None, goals_available=None):
    return FeedSnapshot(
        matches=tuple(matches),
        alerts=tuple(alerts),
        loaded_at=100.0,
        updated_at=time.time(),
        error=error,
        goals_available=goals_available,
    )


def make_match(match_id=1, status=MatchStatus.LIVE, home_goals=1,
               away_goals=0, minute=34, code="PL", index=None,
               kickoff=KICKOFF):
    number = index if index is not None else match_id
    return Match(
        id=match_id,
        competition_id=2021,
        competition_code=code,
        competition_name=competition_label(code),
        home=Team(100 + number, f"TEAM {number:02d} HOME", f"T{number:02d}"[:3]),
        away=Team(200 + number, f"TEAM {number:02d} AWAY", f"A{number:02d}"[:3]),
        kickoff=kickoff,
        status=status,
        minute=minute,
        home_goals=home_goals,
        away_goals=away_goals,
    )


def ars_che():
    return Match(
        id=1001,
        competition_id=2021,
        competition_code="PL",
        competition_name="PREMIER LEAGUE",
        home=Team(57, "ARSENAL FC", "ARS"),
        away=Team(61, "CHELSEA FC", "CHE"),
        kickoff=KICKOFF,
        status=MatchStatus.LIVE,
        minute=34,
        home_goals=2,
        away_goals=1,
        goals=(),
    )


class FakeSports:
    def __init__(self, feed_snapshot, standings=None, configured=True):
        self._snapshot = feed_snapshot
        self.configured = configured
        self.competitions = ("PL", "PD", "BL1", "SA", "FL1")
        self.config = SportsConfig(token="test-token" if configured else "")
        self.standings_by_code = standings or {}
        self.standings_calls = []

    def snapshot(self):
        return self._snapshot

    def standings(self, code):
        self.standings_calls.append(code)
        return self.standings_by_code.get(
            code, Snapshot(loading=True)
        )


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_session(service=None, initial="150", clock=None):
    registry = pages.build_registry()
    kwargs = {"clock": clock} if clock is not None else {}
    session = Session(
        registry,
        profiles.M1,
        initial=pages.INITIAL,
        fallback=registry.get(pages.NOT_FOUND),
        guide=pages.GUIDE,
        services={"sports": service} if service is not None else None,
        **kwargs,
    )
    session.start()
    session.navigate(initial)
    return session


class LivePageTests(unittest.TestCase):
    def test_layout_and_pager(self):
        matches = [
            make_match(index=index, status=MatchStatus.SCHEDULED,
                       home_goals=None, away_goals=None, minute=None)
            for index in range(1, 11)
        ]
        session = make_session(FakeSports(loaded_snapshot(matches)))
        text = session.screen.to_text().splitlines()

        self.assertIn("150 1/1", text[0])
        self.assertEqual(text[1].strip(), "LIVE SCORES - PL")
        self.assertIn("PREMIER LEAGUE", text[2])
        self.assertIn("LIVE 0", text[2])
        self.assertEqual(text[3].strip(), "-" * 40)
        self.assertEqual(text[4].strip(), kickoff_label(KICKOFF))
        self.assertIn("1 T01", text[5][:20])
        self.assertIn("2 T02", text[5][20:])
        self.assertIn("9 T09", text[9][:20])
        self.assertIn("10 T10", text[9][20:])
        self.assertEqual(text[16].strip(), "VIDIPRINTER")
        self.assertIn("TYPE 1-10, THEN ENVOI", text[19])
        self.assertTrue(text[22].startswith("SUITE=NEXT"))
        self.assertIn("153=TABLES", text[23])

    def test_select_match_opens_detail(self):
        session = make_session(FakeSports(loaded_snapshot([ars_che()])))
        session.feed(b"1" + ENVOI)

        self.assertEqual(session.current.number, "151")
        self.assertEqual(session.state["sports_match_id"], 1001)
        text = session.screen.to_text()
        self.assertIn("ARSENAL FC", text)
        self.assertIn("CHELSEA FC", text)
        self.assertIn("2-1", text)

    def test_suite_advances_by_league_and_wraps(self):
        matches = [
            make_match(index=1, code="PL"),
            make_match(index=2, code="PL"),
            make_match(index=3, code="PD"),
            make_match(index=4, code="PD"),
            make_match(index=5, code="BL1"),
            make_match(index=6, code="BL1"),
        ]
        session = make_session(FakeSports(loaded_snapshot(matches)))
        self.assertEqual(
            session.screen.to_text().splitlines()[1].strip(),
            "LIVE SCORES - PL",
        )

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "LIVE SCORES - PD")
        self.assertIn("150 2/3", text[0])

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "LIVE SCORES - BL1")
        self.assertIn("150 3/3", text[0])

        session.feed(SUITE)
        self.assertEqual(
            session.screen.to_text().splitlines()[1].strip(),
            "LIVE SCORES - PL",
        )

    def test_carousel_advances_between_leagues(self):
        matches = [
            make_match(index=1, code="PL"),
            make_match(index=2, code="PD"),
        ]
        clock = FakeClock()
        session = make_session(
            FakeSports(loaded_snapshot(matches)), clock=clock
        )
        self.assertIn("LIVE SCORES - PL", session.screen.to_text())

        clock.advance(30.0)
        session.on_timeout()

        self.assertEqual(session.pager.offset, 1)
        self.assertIn("LIVE SCORES - PD", session.screen.to_text())

    def test_large_league_paginates_within_the_league(self):
        matches = [
            make_match(index=index, status=MatchStatus.SCHEDULED,
                       home_goals=None, away_goals=None, minute=None)
            for index in range(1, 23)
        ]
        session = make_session(FakeSports(loaded_snapshot(matches)))
        text = session.screen.to_text().splitlines()
        self.assertIn("150 1/2", text[0])
        self.assertEqual(text[1].strip(), "LIVE SCORES - PL 1/2")

        session.feed(SUITE)
        text = session.screen.to_text().splitlines()
        self.assertIn("150 2/2", text[0])
        self.assertEqual(text[1].strip(), "LIVE SCORES - PL 2/2")
        self.assertIn("1 T21", text[5][:20])
        self.assertIn("2 T22", text[5][20:])

    def test_invalid_selection_stays(self):
        session = make_session(FakeSports(loaded_snapshot([ars_che()])))
        session.feed(b"5" + ENVOI)
        self.assertEqual(session.current.number, "150")
        self.assertIn("NO MATCH 5.", session.screen.to_text())

    def test_full_page_number_still_routes(self):
        session = make_session(FakeSports(loaded_snapshot([ars_che()])))
        session.feed(b"153" + ENVOI)
        self.assertEqual(session.current.number, "153")

    def test_offline_keeps_scores(self):
        service = FakeSports(
            loaded_snapshot([ars_che()], error="HTTP 500")
        )
        session = make_session(service)
        text = session.screen.to_text()
        self.assertIn("DATA STALE", text)
        self.assertIn("ARS", text)
        self.assertIn("DATA STALE. RETRYING.", text)

    def test_missing_service(self):
        session = make_session(None)
        text = session.screen.to_text()
        self.assertIn("SPORTS FEED NOT CONFIGURED", text)
        self.assertIn("SET FOOTBALL_API_KEY.", text)

    def test_tick_picks_up_background_load_and_cursor(self):
        service = FakeSports(FeedSnapshot(loading=True))
        session = make_session(service)
        self.assertIn("LOADING MATCHES...", session.screen.to_text())

        service._snapshot = loaded_snapshot([ars_che()])
        action = session.tick()
        self.assertIn(codec.pos(20, 6), action.raw)
        self.assertIn(codec.cursor(False), action.raw)
        self.assertIn("ARS", session.screen.to_text())
        self.assertEqual(
            (session.screen.cursor_row, session.screen.cursor_col), (20, 6)
        )

    def test_vidiprinter_shows_alerts(self):
        alert = Alert(KICKOFF, "GOAL", 1001, "ARS", "CHE", 2, 1, 34)
        session = make_session(
            FakeSports(loaded_snapshot([ars_che()], alerts=[alert]))
        )
        self.assertIn("GOAL ARS 2-1 CHE 34'", session.screen.to_text())


class DetailPageTests(unittest.TestCase):
    def test_direct_detail_has_no_match(self):
        session = make_session(
            FakeSports(loaded_snapshot([])), initial="151"
        )
        text = session.screen.to_text()
        self.assertIn("NO MATCH SELECTED.", text)
        self.assertIn("OPEN LIVE SCORES, PICK A NUMBER.", text)

    def test_retour_returns_to_scores(self):
        session = make_session(FakeSports(loaded_snapshot([ars_che()])))
        session.feed(b"1" + ENVOI)
        session.feed(RETOUR)
        self.assertEqual(session.current.number, "150")

    def test_goal_lines(self):
        from services.sports.models import Goal

        base = ars_che()
        match = Match(
            **{
                **base.__dict__,
                "goals": (
                    Goal(22, None, 57, "ARSENAL FC", "BUKAYO SAKA",
                         home_score=1, away_score=0),
                    Goal(55, None, 61, "CHELSEA FC", "COLE PALMER",
                         penalty=True, home_score=1, away_score=1),
                ),
            }
        )
        session = make_session(FakeSports(loaded_snapshot([match])))
        session.feed(b"1" + ENVOI)
        text = session.screen.to_text()
        self.assertIn("BUKAYO SAKA", text)
        self.assertIn("COLE PALMER (P)", text)

    def test_goal_section_is_omitted_when_plan_has_no_events(self):
        finished = make_match(
            index=1, status=MatchStatus.FINISHED, home_goals=1,
            away_goals=0, minute=90,
        )
        session = make_session(
            FakeSports(loaded_snapshot([finished], goals_available=False))
        )
        session.feed(b"1" + ENVOI)
        lines = session.screen.to_text().splitlines()
        self.assertIn("GOAL EVENTS NOT IN YOUR PLAN.", lines[11])
        self.assertNotIn("GOALS", [line.strip() for line in lines])

    def test_scoreless_match_omits_goal_section(self):
        finished = make_match(
            index=1, status=MatchStatus.FINISHED, home_goals=0,
            away_goals=0, minute=90,
        )
        session = make_session(
            FakeSports(loaded_snapshot([finished], goals_available=True))
        )
        session.feed(b"1" + ENVOI)
        lines = session.screen.to_text().splitlines()
        self.assertNotIn("GOALS", [line.strip() for line in lines])
        self.assertNotIn("NO GOALS IN THIS MATCH.", lines)


class TablesPageTests(unittest.TestCase):
    def standings(self):
        rows = (
            StandingRow(1, Team(57, "ARSENAL FC", "ARS"), 10, 13, 25),
            StandingRow(2, Team(65, "MANCHESTER CITY FC", "MCI"), 10, 13, 23),
        )
        return Snapshot(value=rows, loaded_at=time.monotonic())

    def many_standings(self, count=12):
        rows = tuple(
            StandingRow(
                index + 1,
                Team(100 + index, f"TEAM {index + 1:02d}", f"T{index + 1:02d}"),
                10,
                0,
                20 - index,
            )
            for index in range(count)
        )
        return Snapshot(value=rows, loaded_at=time.monotonic())

    def pd_standings(self):
        rows = (
            StandingRow(1, Team(1, "REAL MADRID", "RMA"), 10, 13, 25),
            StandingRow(2, Team(2, "BARCELONA FC", "BAR"), 10, 13, 23),
        )
        return Snapshot(value=rows, loaded_at=time.monotonic())

    def test_table_rows_and_league_change(self):
        service = FakeSports(
            loaded_snapshot([]),
            standings={"PL": self.standings(), "PD": self.pd_standings()},
        )
        session = make_session(service, initial="153")
        text = session.screen.to_text().splitlines()
        self.assertEqual(text[1].strip(), "TABLES")
        self.assertIn("PREMIER LEAGUE", text[2])
        self.assertIn("ARSENAL FC", text[4])
        self.assertIn("25", text[4])
        self.assertIn("1-5 = LEAGUE", text[15])

        session.feed(b"2" + ENVOI)
        self.assertEqual(session.current.number, "153#PD")
        self.assertEqual(session.state["sports_table_code"], "PD")
        self.assertIn("LA LIGA", session.screen.to_text())
        self.assertIn("REAL MADRID", session.screen.to_text())
        self.assertIn("PD", service.standings_calls[-1])

    def test_extension_route_selects_league(self):
        service = FakeSports(
            loaded_snapshot([]),
            standings={"PL": self.standings(), "PD": self.pd_standings()},
        )
        session = make_session(service, initial="153#PD")

        self.assertEqual(session.current.number, "153#PD")
        self.assertEqual(session.state["sports_table_code"], "PD")
        self.assertEqual(service.standings_calls[-1], "PD")
        text = session.screen.to_text()
        self.assertIn("LA LIGA", text)
        self.assertIn("REAL MADRID", text)
        self.assertIn("153#PD", text.splitlines()[0])

    def test_direct_extension_retour_goes_home(self):
        service = FakeSports(
            loaded_snapshot([]), standings={"PL": self.standings()}
        )
        session = make_session(service, initial="153#PL")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, pages.INITIAL)

    def test_selected_extension_retour_returns_to_tables(self):
        service = FakeSports(
            loaded_snapshot([]),
            standings={"PL": self.standings(), "PD": self.pd_standings()},
        )
        session = make_session(service, initial="153")

        session.feed(b"2" + ENVOI)
        self.assertEqual(session.current.number, "153#PD")

        session.feed(RETOUR)
        self.assertEqual(session.current.number, "153")

    def test_invalid_extension_shows_message_and_can_recover(self):
        service = FakeSports(
            loaded_snapshot([]), standings={"PL": self.standings()}
        )
        session = make_session(service, initial="153#ZZZ")

        self.assertEqual(session.current.number, "153#ZZZ")
        self.assertIn("NO LEAGUE ZZZ.", session.screen.to_text())

        session.feed(b"1" + ENVOI)
        self.assertEqual(session.current.number, "153#PL")
        self.assertIn("PREMIER LEAGUE", session.screen.to_text())

    def test_extension_route_survives_pager_moves(self):
        service = FakeSports(
            loaded_snapshot([]),
            standings={"PL": self.many_standings()},
        )
        session = make_session(service, initial="153#PL")
        self.assertIn("153#PL 1/2", session.screen.to_text().splitlines()[0])

        session.feed(SUITE)
        self.assertEqual(session.current.number, "153#PL")
        self.assertIn("153#PL 2/2", session.screen.to_text().splitlines()[0])

    def test_loading_and_missing(self):
        service = FakeSports(loaded_snapshot([]))
        session = make_session(service, initial="153")
        self.assertIn("LOADING TABLE...", session.screen.to_text())

        session = make_session(None, initial="153")
        self.assertIn("SPORTS FEED NOT CONFIGURED", session.screen.to_text())

    def test_error_clears_when_the_pager_moves(self):
        service = FakeSports(
            loaded_snapshot([]),
            standings={"PL": self.many_standings()},
        )
        session = make_session(service, initial="153")
        self.assertIn("153 1/2", session.screen.to_text().splitlines()[0])

        session.feed(b"99" + ENVOI)
        self.assertIn("NO LEAGUE 99.", session.screen.to_text())

        session.feed(SUITE)
        text = session.screen.to_text()
        self.assertIn("153 2/2", text.splitlines()[0])
        self.assertNotIn("NO LEAGUE 99.", text)


class StatusPageTests(unittest.TestCase):
    def test_status_fields(self):
        snapshot = FeedSnapshot(
            loaded_at=100.0,
            updated_at=time.time(),
            quota_remaining=9,
            quota_reset=42,
        )
        session = make_session(FakeSports(snapshot), initial="154")
        text = session.screen.to_text()
        self.assertIn("FOOTBALL-DATA.ORG", text)
        self.assertIn("KEY: SET", text)
        self.assertIn("QUOTA: 9 LEFT", text)
        self.assertIn("PLAN DEPENDENT", text)
        self.assertNotIn("test-token", text)

    def test_not_configured(self):
        session = make_session(None, initial="154")
        text = session.screen.to_text()
        self.assertIn("NOT CONFIGURED", text)
        self.assertIn("FOOTBALL_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
