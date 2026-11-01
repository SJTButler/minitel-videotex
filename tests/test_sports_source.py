import json
import unittest
from pathlib import Path

from minitel.http import JsonResponse
from services.sports.config import DEFAULT_COMPETITIONS
from services.sports.models import MatchStatus
from services.sports.source import (
    FootballDataSource,
    goals_available,
    parse_goals,
    parse_matches,
    parse_score,
    parse_standings,
    parse_status,
)

FIXTURES = Path(__file__).with_name("fixtures")


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class MatchParseTests(unittest.TestCase):
    def test_filters_and_normalises(self):
        matches = parse_matches(
            fixture("football_matches.json"), DEFAULT_COMPETITIONS
        )
        self.assertEqual(len(matches), 5)
        by_id = {match.id: match for match in matches}
        self.assertNotIn(1006, by_id)

        live = by_id[1001]
        self.assertEqual(live.competition_code, "PL")
        self.assertEqual(live.home.short, "ARS")
        self.assertEqual(live.away.short, "CHE")
        self.assertEqual(live.status, MatchStatus.LIVE)
        self.assertEqual((live.home_goals, live.away_goals), (1, 0))
        self.assertEqual(live.minute, 34)
        self.assertEqual(len(live.goals), 1)
        self.assertEqual(live.goals[0].scorer, "BUKAYO SAKA")

        paused = by_id[1004]
        self.assertEqual(paused.status, MatchStatus.HALF_TIME)
        self.assertEqual(paused.injury_time, 2)

        timed = by_id[1002]
        self.assertEqual(timed.status, MatchStatus.SCHEDULED)
        self.assertIsNone(timed.home_goals)
        self.assertEqual(timed.home.short, "RMA")

    def test_sorted_by_kickoff(self):
        matches = parse_matches(
            fixture("football_matches.json"), DEFAULT_COMPETITIONS
        )
        kickoffs = [match.kickoff for match in matches]
        self.assertEqual(kickoffs, sorted(kickoffs))

    def test_status_mapping(self):
        self.assertIs(parse_status("IN_PLAY"), MatchStatus.LIVE)
        self.assertIs(parse_status("PAUSED"), MatchStatus.HALF_TIME)
        self.assertIs(parse_status("TIMED"), MatchStatus.SCHEDULED)
        self.assertIs(parse_status("FINISHED"), MatchStatus.FINISHED)
        self.assertIs(parse_status("POSTPONED"), MatchStatus.POSTPONED)
        self.assertIs(parse_status("SUSPENDED"), MatchStatus.POSTPONED)
        self.assertIs(parse_status("CANCELLED"), MatchStatus.CANCELLED)
        self.assertIs(parse_status("SOMETHING"), MatchStatus.UNKNOWN)
        self.assertIs(parse_status(None), MatchStatus.UNKNOWN)

    def test_score_falls_back_to_half_time(self):
        home, away = parse_score(
            {
                "fullTime": {"home": None, "away": None},
                "halfTime": {"home": 1, "away": 0},
            }
        )
        self.assertEqual((home, away), (1, 0))

    def test_goal_types(self):
        goals = parse_goals(
            {
                "goals": [
                    {
                        "minute": 10,
                        "type": "OWN",
                        "team": {"id": 1, "name": "Home"},
                        "scorer": {"name": "Defender"},
                        "score": {"home": 1, "away": 0},
                    },
                    {
                        "minute": 20,
                        "type": "PENALTY",
                        "team": {"id": 2, "name": "Away"},
                        "scorer": {"name": "Forward"},
                        "score": {"home": 1, "away": 1},
                    },
                ]
            }
        )
        self.assertTrue(goals[0].own_goal)
        self.assertFalse(goals[0].penalty)
        self.assertTrue(goals[1].penalty)
        self.assertEqual(goals[1].scorer, "FORWARD")

    def test_invalid_payloads(self):
        self.assertEqual(parse_matches(None, DEFAULT_COMPETITIONS), ())
        self.assertEqual(parse_matches({"matches": None}), ())
        self.assertEqual(parse_matches({"matches": [{"id": 1}]}), ())

    def test_goals_available(self):
        self.assertTrue(goals_available(fixture("football_matches.json")))
        self.assertFalse(goals_available({"matches": [{"id": 1}]}))
        self.assertIsNone(goals_available({}))
        self.assertIsNone(goals_available({"matches": []}))


class StandingParseTests(unittest.TestCase):
    def test_total_table(self):
        rows = parse_standings(fixture("football_standings.json"))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0].position, 1)
        self.assertEqual(rows[0].team.short, "ARS")
        self.assertEqual(rows[0].played, 10)
        self.assertEqual(rows[0].goal_difference, 13)
        self.assertEqual(rows[0].points, 25)

    def test_bad_payload(self):
        self.assertEqual(parse_standings(None), ())
        self.assertEqual(parse_standings({"standings": None}), ())
        self.assertEqual(parse_standings({"standings": [{}]}), ())


class SourceRequestTests(unittest.TestCase):
    def test_day_request(self):
        seen = {}
        payload = fixture("football_matches.json")

        def fake_get_json(url, headers=None, timeout=None):
            seen["url"] = url
            seen["headers"] = dict(headers or {})
            seen["timeout"] = timeout
            return JsonResponse(
                payload,
                status=200,
                headers={
                    "x-requests-available-minute": "9",
                    "X-RequestCounter-Reset": "42",
                },
            )

        source = FootballDataSource(
            "secret-token",
            competitions=("PL", "PD"),
            get_json_response=fake_get_json,
            timeout=3.0,
        )
        result = source.fetch_day("2026-11-01")

        self.assertIn("/matches?date=2026-11-01", seen["url"])
        self.assertIn("competitions=PL,PD", seen["url"])
        self.assertEqual(seen["headers"]["X-Auth-Token"], "secret-token")
        self.assertEqual(seen["headers"]["X-Unfold-Goals"], "true")
        self.assertEqual(seen["timeout"], 3.0)
        self.assertEqual(result.quota_remaining, 9)
        self.assertEqual(result.quota_reset, 42)
        self.assertEqual(len(result.value), 2)

    def test_documented_quota_alias(self):
        def fake_get_json(url, headers=None, timeout=None):
            return JsonResponse(
                fixture("football_matches.json"),
                headers={"X-RequestsAvailable": "7"},
            )

        source = FootballDataSource(
            "secret-token", get_json_response=fake_get_json
        )
        result = source.fetch_day("2026-11-01")
        self.assertEqual(result.quota_remaining, 7)

    def test_standings_request(self):
        seen = {}

        def fake_get_json(url, headers=None, timeout=None):
            seen["url"] = url
            seen["headers"] = dict(headers or {})
            return JsonResponse(
                fixture("football_standings.json"),
                headers={"X-RequestsAvailable": "8"},
            )

        source = FootballDataSource(
            "secret-token", get_json_response=fake_get_json
        )
        result = source.fetch_standings("PL")

        self.assertEqual(
            seen["url"],
            "https://api.football-data.org/v4/competitions/PL/standings",
        )
        self.assertNotIn("X-Unfold-Goals", seen["headers"])
        self.assertEqual(result.quota_remaining, 8)
        self.assertEqual(len(result.value), 4)


if __name__ == "__main__":
    unittest.main()
