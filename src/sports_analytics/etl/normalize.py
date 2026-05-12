from __future__ import annotations

import pandas as pd


DATE_COLUMNS = {
    "date",
    "transfer_date",
    "date_of_birth",
    "contract_expiration_date",
}

NUMERIC_COLUMNS = {
    "game_id",
    "player_id",
    "player_club_id",
    "player_current_club_id",
    "club_id",
    "opponent_id",
    "home_club_id",
    "away_club_id",
    "home_club_goals",
    "away_club_goals",
    "own_goals",
    "opponent_goals",
    "yellow_cards",
    "red_cards",
    "goals",
    "assists",
    "minutes_played",
    "season",
    "minute",
    "player_in_id",
    "player_assist_id",
    "market_value_in_eur",
    "highest_market_value_in_eur",
    "transfer_fee",
    "number",
    "team_captain",
    "attendance",
    "stadium_seats",
    "squad_size",
    "average_age",
    "foreigners_number",
    "foreigners_percentage",
    "national_team_players",
    "international_caps",
    "international_goals",
}

BOOLEAN_COLUMNS = {
    "is_win",
    "team_captain",
}

TEXT_COLUMNS_TO_NORMALIZE = {
    "name",
    "player_name",
    "club_name",
    "home_club_name",
    "away_club_name",
    "opponent_name",
    "referee",
    "competition_id",
    "competition_type",
    "type",
    "position",
    "hosting",
}


def normalize_dataframe(table_name: str, dataframe: pd.DataFrame, source_file: str | None = None) -> pd.DataFrame:
    """Aplica limpieza segura y tipado minimo para que los KPIs usen datos consistentes."""
    data = dataframe.copy()
    data.columns = [column.strip() for column in data.columns]

    for column in data.select_dtypes(include=["object"]).columns:
        data[column] = data[column].map(_clean_text_value)

    for column in data.columns:
        if column in DATE_COLUMNS or column.endswith("_date"):
            data[column] = pd.to_datetime(data[column], errors="coerce")
        elif column in NUMERIC_COLUMNS:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    for column in BOOLEAN_COLUMNS.intersection(data.columns):
        data[column] = data[column].map(_normalize_boolean)

    if "minutes_played" in data.columns:
        data["minutes_played"] = data["minutes_played"].clip(lower=0, upper=130)

    if {"home_club_goals", "away_club_goals"}.issubset(data.columns):
        data["home_club_goals"] = data["home_club_goals"].clip(lower=0)
        data["away_club_goals"] = data["away_club_goals"].clip(lower=0)

    for column in ("yellow_cards", "red_cards", "goals", "assists"):
        if column in data.columns:
            data[column] = data[column].fillna(0).clip(lower=0)

    if source_file is not None:
        data["_source_table"] = table_name
        data["_source_file"] = source_file

    return data


def _clean_text_value(value: object) -> object:
    if not isinstance(value, str):
        return value

    cleaned = " ".join(value.strip().split())
    return pd.NA if cleaned == "" else cleaned


def _normalize_boolean(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "si", "sí", "home", "h"}:
        return True
    if text in {"0", "false", "no", "away", "a"}:
        return False
    return value
