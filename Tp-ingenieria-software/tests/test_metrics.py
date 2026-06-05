import unittest

import pandas as pd

from sports_analytics.metrics.teams import (
    add_team_discipline,
    build_team_match_view,
    compare_teams,
    head_to_head_summary,
    summarize_head_to_head_by_team,
)


class TeamMetricsTest(unittest.TestCase):
    def test_compare_teams_and_red_card_impact_data_is_preserved(self):
        games = pd.DataFrame(
            [
                {
                    "game_id": 1,
                    "date": "2024-01-01",
                    "season": 2024,
                    "competition_id": "L1",
                    "home_club_id": 10,
                    "away_club_id": 20,
                    "home_club_name": "Local",
                    "away_club_name": "Visitante",
                    "home_club_goals": 2,
                    "away_club_goals": 1,
                }
            ]
        )
        appearances = pd.DataFrame(
            [
                {"game_id": 1, "player_club_id": 10, "red_cards": 1},
                {"game_id": 1, "player_club_id": 10, "red_cards": 0, "yellow_cards": 2},
                {"game_id": 1, "player_club_id": 20, "red_cards": 0, "yellow_cards": 1},
            ]
        )

        matches = add_team_discipline(build_team_match_view(games), appearances)
        comparison = compare_teams(matches, 10, 20)

        self.assertEqual(comparison.loc[comparison["team_id"] == 10, "win_rate"].iloc[0], 1.0)
        self.assertEqual(matches.loc[matches["team_id"] == 10, "team_red_cards"].iloc[0], 1)
        self.assertEqual(matches.loc[matches["team_id"] == 10, "team_yellow_cards"].iloc[0], 2)
        self.assertEqual(matches.loc[matches["team_id"] == 20, "team_red_cards"].iloc[0], 0)

    def test_compare_teams_ignores_future_or_unfinished_matches(self):
        games = pd.DataFrame(
            [
                {
                    "game_id": 1,
                    "date": "2024-01-01",
                    "season": 2024,
                    "competition_id": "L1",
                    "home_club_id": 10,
                    "away_club_id": 20,
                    "home_club_name": "Local",
                    "away_club_name": "Visitante",
                    "home_club_goals": 2,
                    "away_club_goals": 1,
                },
                {
                    "game_id": 2,
                    "date": "2999-01-01",
                    "season": 2999,
                    "competition_id": "L1",
                    "home_club_id": 10,
                    "away_club_id": 20,
                    "home_club_name": "Local",
                    "away_club_name": "Visitante",
                    "home_club_goals": 0,
                    "away_club_goals": 0,
                },
            ]
        )

        comparison = compare_teams(build_team_match_view(games), 10, 20)

        team_a = comparison[comparison["team_id"] == 10].iloc[0]
        team_b = comparison[comparison["team_id"] == 20].iloc[0]
        self.assertEqual(team_a["played"], 1)
        self.assertEqual(team_a["wins"], 1)
        self.assertEqual(team_a["recent_form"], "W")
        self.assertEqual(team_b["played"], 1)
        self.assertEqual(team_b["losses"], 1)
        self.assertEqual(team_b["recent_form"], "L")

    def test_head_to_head_summary_counts_wins_draws_and_percentages(self):
        games = pd.DataFrame(
            [
                {
                    "game_id": 1,
                    "date": "2024-01-01",
                    "season": 2024,
                    "competition_id": "L1",
                    "home_club_id": 10,
                    "away_club_id": 20,
                    "home_club_name": "A",
                    "away_club_name": "B",
                    "home_club_goals": 2,
                    "away_club_goals": 1,
                },
                {
                    "game_id": 2,
                    "date": "2024-02-01",
                    "season": 2024,
                    "competition_id": "L1",
                    "home_club_id": 20,
                    "away_club_id": 10,
                    "home_club_name": "B",
                    "away_club_name": "A",
                    "home_club_goals": 3,
                    "away_club_goals": 0,
                },
                {
                    "game_id": 3,
                    "date": "2024-03-01",
                    "season": 2024,
                    "competition_id": "L1",
                    "home_club_id": 10,
                    "away_club_id": 20,
                    "home_club_name": "A",
                    "away_club_name": "B",
                    "home_club_goals": 1,
                    "away_club_goals": 1,
                },
            ]
        )

        summary = head_to_head_summary(games, 10, 20)

        self.assertEqual(summary["played"], 3)
        self.assertEqual(summary["team_a_wins"], 1)
        self.assertEqual(summary["draws"], 1)
        self.assertEqual(summary["team_b_wins"], 1)
        self.assertEqual(summary["team_a_win_rate"], 0.333)
        self.assertEqual(summary["draw_rate"], 0.333)
        self.assertEqual(summary["team_b_win_rate"], 0.333)

    def test_head_to_head_by_team_adds_discipline_kpis(self):
        games = pd.DataFrame(
            [
                {
                    "game_id": 1,
                    "date": "2024-01-01",
                    "season": 2024,
                    "competition_id": "L1",
                    "home_club_id": 10,
                    "away_club_id": 20,
                    "home_club_name": "A",
                    "away_club_name": "B",
                    "home_club_goals": 2,
                    "away_club_goals": 1,
                },
                {
                    "game_id": 2,
                    "date": "2024-02-01",
                    "season": 2024,
                    "competition_id": "L1",
                    "home_club_id": 20,
                    "away_club_id": 10,
                    "home_club_name": "B",
                    "away_club_name": "A",
                    "home_club_goals": 0,
                    "away_club_goals": 0,
                },
            ]
        )
        appearances = pd.DataFrame(
            [
                {"game_id": 1, "player_club_id": 10, "yellow_cards": 2, "red_cards": 0},
                {"game_id": 1, "player_club_id": 20, "yellow_cards": 4, "red_cards": 1},
                {"game_id": 2, "player_club_id": 10, "yellow_cards": 1, "red_cards": 0},
                {"game_id": 2, "player_club_id": 20, "yellow_cards": 3, "red_cards": 0},
            ]
        )

        matches = add_team_discipline(build_team_match_view(games), appearances)
        summary = summarize_head_to_head_by_team(matches, 10, 20)

        team_a = summary[summary["team_id"] == 10].iloc[0]
        team_b = summary[summary["team_id"] == 20].iloc[0]
        self.assertEqual(team_a["played"], 2)
        self.assertEqual(team_a["wins"], 1)
        self.assertEqual(team_a["avg_yellow_cards"], 1.5)
        self.assertEqual(team_b["avg_yellow_cards"], 3.5)
        self.assertEqual(team_b["avg_red_cards"], 0.5)


if __name__ == "__main__":
    unittest.main()
