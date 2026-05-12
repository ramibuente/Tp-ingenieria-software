from __future__ import annotations

import pandas as pd


PLAYER_APPEARANCE_COLUMNS = [
    "appearance_id",
    "game_id",
    "player_id",
    "player_club_id",
    "date",
    "player_name",
    "competition_id",
    "yellow_cards",
    "red_cards",
    "goals",
    "assists",
    "minutes_played",
]

PLAYER_LINEUP_COLUMNS = [
    "game_id",
    "player_id",
    "club_id",
    "type",
    "position",
    "team_captain",
]

PLAYER_EVENT_COLUMNS = [
    "game_id",
    "minute",
    "type",
    "player_id",
    "player_in_id",
    "description",
]


def build_player_summary(appearances: pd.DataFrame) -> pd.DataFrame:
    data = appearances[PLAYER_APPEARANCE_COLUMNS].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")

    summary = (
        data.groupby(["player_id", "player_name"], dropna=False)
        .agg(
            matches=("game_id", "nunique"),
            minutes=("minutes_played", "sum"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            yellow_cards=("yellow_cards", "sum"),
            red_cards=("red_cards", "sum"),
            first_match=("date", "min"),
            last_match=("date", "max"),
        )
        .reset_index()
    )
    summary["goal_contributions"] = summary["goals"] + summary["assists"]
    summary["goals_per_90"] = _per_90(summary["goals"], summary["minutes"])
    summary["assists_per_90"] = _per_90(summary["assists"], summary["minutes"])
    summary["contributions_per_90"] = _per_90(summary["goal_contributions"], summary["minutes"])
    summary["cards_per_90"] = _per_90(summary["yellow_cards"] + summary["red_cards"], summary["minutes"])
    return summary.sort_values(["goal_contributions", "minutes"], ascending=False)


def player_history(appearances: pd.DataFrame, player_id: int) -> pd.DataFrame:
    data = appearances[appearances["player_id"] == player_id].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["goal_contributions"] = data["goals"] + data["assists"]
    return data.sort_values("date", ascending=False)


def enrich_player_history(player_matches: pd.DataFrame, games: pd.DataFrame, lineups: pd.DataFrame) -> pd.DataFrame:
    game_columns = [
        "game_id",
        "home_club_id",
        "away_club_id",
        "home_club_name",
        "away_club_name",
        "home_club_formation",
        "away_club_formation",
    ]
    enriched = player_matches.merge(games[game_columns], on="game_id", how="left")
    enriched["opponent_name"] = enriched.apply(_resolve_opponent_name, axis=1)
    enriched["team_formation"] = enriched.apply(_resolve_team_formation, axis=1)

    if not lineups.empty:
        enriched = enriched.merge(
            lineups[PLAYER_LINEUP_COLUMNS],
            on=["game_id", "player_id"],
            how="left",
            suffixes=("", "_lineup"),
        )
    else:
        enriched["type"] = pd.NA
        enriched["position"] = pd.NA
        enriched["team_captain"] = pd.NA

    enriched["lineup_role"] = enriched["type"].replace(
        {"starting_lineup": "Titular", "substitutes": "Suplente"}
    ).fillna("Sin dato")
    return enriched


def player_vs_opponent(enriched_history: pd.DataFrame, opponent_name: str | None = None) -> pd.DataFrame:
    data = enriched_history.copy()
    if opponent_name:
        data = data[data["opponent_name"] == opponent_name]

    summary = (
        data.groupby("opponent_name", dropna=False)
        .agg(
            matches=("game_id", "nunique"),
            minutes=("minutes_played", "sum"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
        )
        .reset_index()
        .sort_values(["goals", "assists", "matches"], ascending=False)
    )
    if summary.empty:
        return summary
    summary["goals_per_match"] = (summary["goals"] / summary["matches"].replace(0, pd.NA)).fillna(0).round(2)
    summary["goals_per_90"] = _per_90(summary["goals"], summary["minutes"])
    return summary


def player_role_summary(enriched_history: pd.DataFrame) -> pd.DataFrame:
    summary = (
        enriched_history.groupby("lineup_role", dropna=False)
        .agg(
            matches=("game_id", "nunique"),
            minutes=("minutes_played", "sum"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
        )
        .reset_index()
    )
    summary["contributions_per_90"] = _per_90(summary["goals"] + summary["assists"], summary["minutes"])
    return summary.sort_values("matches", ascending=False)


def player_formation_summary(enriched_history: pd.DataFrame) -> pd.DataFrame:
    summary = (
        enriched_history.dropna(subset=["team_formation"])
        .groupby("team_formation", as_index=False)
        .agg(
            matches=("game_id", "nunique"),
            minutes=("minutes_played", "sum"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
        )
        .sort_values(["matches", "goals"], ascending=False)
    )
    if summary.empty:
        return summary
    summary["contributions_per_90"] = _per_90(summary["goals"] + summary["assists"], summary["minutes"])
    return summary


def player_substitution_summary(events: pd.DataFrame, player_id: int) -> dict[str, int]:
    if events.empty:
        return {"substituted_in": 0, "substituted_out": 0}

    substitutions = events[events["type"] == "Substitutions"].copy()
    return {
        "substituted_in": int((substitutions["player_in_id"] == player_id).sum()),
        "substituted_out": int((substitutions["player_id"] == player_id).sum()),
    }


def player_season_summary(player_matches: pd.DataFrame) -> pd.DataFrame:
    data = player_matches.copy()
    data["season"] = data["date"].dt.year
    season_summary = (
        data.groupby("season", dropna=False)
        .agg(
            matches=("game_id", "nunique"),
            minutes=("minutes_played", "sum"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            yellow_cards=("yellow_cards", "sum"),
            red_cards=("red_cards", "sum"),
        )
        .reset_index()
        .sort_values("season")
    )
    season_summary["goals_per_90"] = _per_90(season_summary["goals"], season_summary["minutes"])
    season_summary["assists_per_90"] = _per_90(season_summary["assists"], season_summary["minutes"])
    return season_summary


def _per_90(value: pd.Series, minutes: pd.Series) -> pd.Series:
    safe_minutes = minutes.replace(0, pd.NA)
    return ((value / safe_minutes) * 90).fillna(0).round(2)


def _resolve_opponent_name(row: pd.Series) -> object:
    if row["player_club_id"] == row["home_club_id"]:
        return row["away_club_name"]
    if row["player_club_id"] == row["away_club_id"]:
        return row["home_club_name"]
    return pd.NA


def _resolve_team_formation(row: pd.Series) -> object:
    if row["player_club_id"] == row["home_club_id"]:
        return row["home_club_formation"]
    if row["player_club_id"] == row["away_club_id"]:
        return row["away_club_formation"]
    return pd.NA
