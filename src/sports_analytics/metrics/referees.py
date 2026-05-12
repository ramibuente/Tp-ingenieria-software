from __future__ import annotations

import pandas as pd


REFEREE_GAME_COLUMNS = [
    "game_id",
    "date",
    "season",
    "competition_id",
    "home_club_id",
    "away_club_id",
    "home_club_name",
    "away_club_name",
    "home_club_goals",
    "away_club_goals",
    "referee",
]

CARD_COLUMNS = ["game_id", "yellow_cards", "red_cards"]
PENALTY_EVENT_COLUMNS = ["game_id", "type", "description"]


def build_referee_match_view(
    games: pd.DataFrame,
    appearances: pd.DataFrame,
    events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    referee_games = games[REFEREE_GAME_COLUMNS].dropna(subset=["referee"]).copy()
    referee_games["date"] = pd.to_datetime(referee_games["date"], errors="coerce")
    referee_games["total_goals"] = referee_games["home_club_goals"] + referee_games["away_club_goals"]
    referee_games["home_win"] = referee_games["home_club_goals"] > referee_games["away_club_goals"]
    referee_games["draw"] = referee_games["home_club_goals"] == referee_games["away_club_goals"]
    referee_games["away_win"] = referee_games["home_club_goals"] < referee_games["away_club_goals"]

    cards_by_game = (
        appearances[CARD_COLUMNS]
        .groupby("game_id", as_index=False)
        .agg(yellow_cards=("yellow_cards", "sum"), red_cards=("red_cards", "sum"))
    )
    referee_games = referee_games.merge(cards_by_game, on="game_id", how="left")
    referee_games[["yellow_cards", "red_cards"]] = referee_games[["yellow_cards", "red_cards"]].fillna(0)
    referee_games["had_red_card"] = referee_games["red_cards"] > 0

    if events is not None and not events.empty:
        penalty_events = events[events["description"].astype(str).str.contains("penalty", case=False, na=False)]
        penalties_by_game = (
            penalty_events.groupby("game_id", as_index=False)
            .agg(penalties=("description", "count"))
        )
        referee_games = referee_games.merge(penalties_by_game, on="game_id", how="left")
    else:
        referee_games["penalties"] = 0

    referee_games["penalties"] = referee_games["penalties"].fillna(0)
    return referee_games.sort_values("date")


def build_referee_summary(referee_matches: pd.DataFrame) -> pd.DataFrame:
    summary = (
        referee_matches.groupby("referee", dropna=False)
        .agg(
            matches=("game_id", "nunique"),
            avg_goals=("total_goals", "mean"),
            avg_yellow_cards=("yellow_cards", "mean"),
            avg_red_cards=("red_cards", "mean"),
            red_card_frequency=("had_red_card", "mean"),
            avg_penalties=("penalties", "mean"),
            total_penalties=("penalties", "sum"),
            home_win_rate=("home_win", "mean"),
            draw_rate=("draw", "mean"),
            away_win_rate=("away_win", "mean"),
            first_match=("date", "min"),
            last_match=("date", "max"),
        )
        .reset_index()
    )

    numeric_columns = [
        "avg_goals",
        "avg_yellow_cards",
        "avg_red_cards",
        "red_card_frequency",
        "avg_penalties",
        "home_win_rate",
        "draw_rate",
        "away_win_rate",
    ]
    summary[numeric_columns] = summary[numeric_columns].round(3)
    return summary.sort_values(["matches", "last_match"], ascending=False)


def referee_history(referee_matches: pd.DataFrame, referee: str) -> pd.DataFrame:
    return referee_matches[referee_matches["referee"] == referee].sort_values("date", ascending=False)


def referee_team_history(referee_matches: pd.DataFrame, referee: str, team_id: int) -> pd.DataFrame:
    history = referee_history(referee_matches, referee)
    return history[(history["home_club_id"] == team_id) | (history["away_club_id"] == team_id)].sort_values(
        "date",
        ascending=False,
    )
