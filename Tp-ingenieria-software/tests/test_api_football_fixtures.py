import unittest
from unittest.mock import patch

import pandas as pd

from sports_analytics.ingestion.api_football_fixtures import (
    build_fixture_quality_report,
    normalize_fixture_payload,
)
from sports_analytics.services.api_football import ApiFootballError, fetch_fixtures_payload
from sports_analytics.services.team_matching import build_team_name_index, find_best_team_match


class ApiFootballFixturesTest(unittest.TestCase):
    def test_normalize_fixture_payload_flattens_api_response(self):
        raw = {
            "ingested_at": "2024-05-19T18:00:00+00:00",
            "endpoint": "/fixtures",
            "params": {"league": 128, "season": 2024, "next": 2},
            "payload": {
                "response": [
                    {
                        "fixture": {
                            "id": 123,
                            "date": "2024-05-20T21:00:00+00:00",
                            "timestamp": 1716238800,
                            "timezone": "America/Argentina/Buenos_Aires",
                            "status": {"short": "NS", "long": "Not Started"},
                            "venue": {"name": "Estadio Demo", "city": "La Plata"},
                        },
                        "league": {"id": 128, "name": "Liga Demo", "season": 2024, "round": "Fecha 1"},
                        "teams": {
                            "home": {"id": 10, "name": "Equipo A"},
                            "away": {"id": 20, "name": "Equipo B"},
                        },
                        "goals": {"home": None, "away": None},
                    }
                ]
            },
        }

        fixtures = normalize_fixture_payload(raw)

        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures.iloc[0]["fixture_id"], 123)
        self.assertEqual(fixtures.iloc[0]["league_id"], 128)
        self.assertEqual(fixtures.iloc[0]["home_team_name"], "Equipo A")
        self.assertEqual(fixtures.iloc[0]["away_team_name"], "Equipo B")
        self.assertIn('"league": 128', fixtures.iloc[0]["source_params"])

    def test_fetch_fixtures_rejects_seasons_after_2024_before_request(self):
        with patch("sports_analytics.services.api_football.requests.get") as requests_get:
            with self.assertRaisesRegex(ApiFootballError, "hasta 2024"):
                fetch_fixtures_payload(league_id=128, season=2025, api_key="demo")

        requests_get.assert_not_called()

    def test_quality_report_flags_duplicate_fixture_ids(self):
        fixtures = pd.DataFrame(
            [
                {
                    "fixture_id": 123,
                    "fixture_date": "2024-05-20",
                    "league_id": 128,
                    "season": 2024,
                    "home_team_id": 10,
                    "home_team_name": "Equipo A",
                    "away_team_id": 20,
                    "away_team_name": "Equipo B",
                    "status_short": "NS",
                },
                {
                    "fixture_id": 123,
                    "fixture_date": "2024-05-21",
                    "league_id": 128,
                    "season": 2024,
                    "home_team_id": 30,
                    "home_team_name": "Equipo C",
                    "away_team_id": 40,
                    "away_team_name": "Equipo D",
                    "status_short": "NS",
                },
            ]
        )

        report = build_fixture_quality_report(fixtures)

        self.assertIn("duplicated_fixture_id", set(report["issue"]))

    def test_team_matching_handles_api_football_name_variants(self):
        games = pd.DataFrame(
            [
                {
                    "home_club_id": 1286,
                    "home_club_name": "Club Atlético Newell’s Old Boys",
                    "away_club_id": 928,
                    "away_club_name": "Club Atlético Platense",
                },
                {
                    "home_club_id": 1030,
                    "home_club_name": "Asociación Atlética Argentinos Juniors",
                    "away_club_id": 1418,
                    "away_club_name": "Club Atlético Rosario Central",
                },
                {
                    "home_club_id": 1829,
                    "home_club_name": "Instituto Atlético Central Córdoba",
                    "away_club_id": 12454,
                    "away_club_name": "Club Atlético Sarmiento",
                },
                {
                    "home_club_id": 1184,
                    "home_club_name": "Koninklijke Racing Club Genk",
                    "away_club_id": 69359,
                    "away_club_name": "CF Independiente Alicante",
                },
                {
                    "home_club_id": 1444,
                    "home_club_name": "Racing Club Asociación Civil de Avellaneda",
                    "away_club_id": 1234,
                    "away_club_name": "Club Atlético Independiente de Avellaneda",
                },
            ]
        )
        index = build_team_name_index(games)

        self.assertEqual(find_best_team_match("Newells Old Boys", index).team_id, 1286)
        self.assertEqual(find_best_team_match("Platense", index).team_id, 928)
        self.assertEqual(find_best_team_match("Argentinos JRS", index).team_id, 1030)
        self.assertEqual(find_best_team_match("Rosario Central", index).team_id, 1418)
        self.assertEqual(find_best_team_match("Instituto Cordoba", index).team_id, 1829)
        self.assertEqual(find_best_team_match("Sarmiento Junin", index).team_id, 12454)
        self.assertEqual(find_best_team_match("Racing Club", index).team_id, 1444)
        self.assertEqual(find_best_team_match("Independiente", index).team_id, 1234)


if __name__ == "__main__":
    unittest.main()
