from __future__ import annotations

import pandas as pd


REQUIRED_GAME_COLUMNS = [
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
]

TEAM_DISCIPLINE_COLUMNS = ["game_id", "player_club_id", "red_cards"]


def build_team_match_view(games: pd.DataFrame) -> pd.DataFrame:
    games = games[REQUIRED_GAME_COLUMNS].copy()
    games["date"] = pd.to_datetime(games["date"], errors="coerce")

    home = games.rename(
        columns={
            "home_club_id": "team_id",
            "home_club_name": "team_name",
            "away_club_id": "opponent_id",
            "away_club_name": "opponent_name",
            "home_club_goals": "goals_for",
            "away_club_goals": "goals_against",
        }
    )
    home["is_home"] = True

    away = games.rename(
        columns={
            "away_club_id": "team_id",
            "away_club_name": "team_name",
            "home_club_id": "opponent_id",
            "home_club_name": "opponent_name",
            "away_club_goals": "goals_for",
            "home_club_goals": "goals_against",
        }
    )
    away["is_home"] = False

    columns = [
        "game_id",
        "date",
        "season",
        "competition_id",
        "team_id",
        "team_name",
        "opponent_id",
        "opponent_name",
        "goals_for",
        "goals_against",
        "is_home",
    ]
    matches = pd.concat([home[columns], away[columns]], ignore_index=True)
    matches["total_goals"] = matches["goals_for"] + matches["goals_against"]
    matches["won"] = matches["goals_for"] > matches["goals_against"]
    matches["draw"] = matches["goals_for"] == matches["goals_against"]
    matches["lost"] = matches["goals_for"] < matches["goals_against"]
    matches["btts"] = (matches["goals_for"] > 0) & (matches["goals_against"] > 0)
    matches["over_2_5"] = matches["total_goals"] > 2.5
    return matches.sort_values("date")


def add_team_discipline(matches: pd.DataFrame, appearances: pd.DataFrame) -> pd.DataFrame:
    if not set(TEAM_DISCIPLINE_COLUMNS).issubset(appearances.columns):
        output = matches.copy()
        output["team_red_cards"] = 0
        output["had_red_card"] = False
        return output

    red_cards = (
        appearances[TEAM_DISCIPLINE_COLUMNS]
        .groupby(["game_id", "player_club_id"], as_index=False)
        .agg(team_red_cards=("red_cards", "sum"))
        .rename(columns={"player_club_id": "team_id"})
    )
    output = matches.merge(red_cards, on=["game_id", "team_id"], how="left")
    output["team_red_cards"] = output["team_red_cards"].fillna(0)
    output["had_red_card"] = output["team_red_cards"] > 0
    return output


def filter_team_matches(matches: pd.DataFrame, team_id: int, last_n: int | None = None) -> pd.DataFrame:
    team_matches = matches[matches["team_id"] == team_id].sort_values("date")
    if last_n is not None:
        team_matches = team_matches.tail(last_n)
    return team_matches


def summarize_team(matches: pd.DataFrame, team_id: int, last_n: int | None = None) -> dict[str, object]:
    team_matches = filter_team_matches(matches, team_id, last_n)
    played = len(team_matches)

    if played == 0:
        return {
            "team_id": team_id,
            "played": 0,
            "win_rate": 0.0,
            "avg_goals_for": 0.0,
            "avg_goals_against": 0.0,
            "over_2_5_rate": 0.0,
            "btts_rate": 0.0,
            "recent_form": "",
        }

    recent_form = "".join(
        "W" if row.won else "D" if row.draw else "L"
        for row in team_matches.tail(5).itertuples()
    )

    return {
        "team_id": team_id,
        "team_name": team_matches["team_name"].dropna().iloc[-1],
        "played": played,
        "wins": int(team_matches["won"].sum()),
        "draws": int(team_matches["draw"].sum()),
        "losses": int(team_matches["lost"].sum()),
        "win_rate": round(float(team_matches["won"].mean()), 3),
        "avg_goals_for": round(float(team_matches["goals_for"].mean()), 2),
        "avg_goals_against": round(float(team_matches["goals_against"].mean()), 2),
        "over_2_5_rate": round(float(team_matches["over_2_5"].mean()), 3),
        "btts_rate": round(float(team_matches["btts"].mean()), 3),
        "avg_total_goals": round(float(team_matches["total_goals"].mean()), 2),
        "recent_form": recent_form,
    }


def head_to_head(games: pd.DataFrame, team_a_id: int, team_b_id: int) -> pd.DataFrame:
    mask_a_home = (games["home_club_id"] == team_a_id) & (games["away_club_id"] == team_b_id)
    mask_b_home = (games["home_club_id"] == team_b_id) & (games["away_club_id"] == team_a_id)
    return games[mask_a_home | mask_b_home].sort_values("date", ascending=False)


def head_to_head_summary(games: pd.DataFrame, team_a_id: int, team_b_id: int) -> dict[str, object]:
    h2h = head_to_head(games, team_a_id, team_b_id).copy()
    if h2h.empty:
        return _empty_head_to_head_summary(team_a_id, team_b_id)

    h2h["date"] = pd.to_datetime(h2h["date"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    completed = h2h[
        h2h["home_club_goals"].notna()
        & h2h["away_club_goals"].notna()
        & (h2h["date"].isna() | (h2h["date"] <= today))
    ].copy()

    played = len(completed)
    if played == 0:
        return _empty_head_to_head_summary(team_a_id, team_b_id)

    home_wins = completed["home_club_goals"] > completed["away_club_goals"]
    away_wins = completed["away_club_goals"] > completed["home_club_goals"]
    draws = completed["home_club_goals"] == completed["away_club_goals"]

    team_a_wins = int(
        (
            ((completed["home_club_id"] == team_a_id) & home_wins)
            | ((completed["away_club_id"] == team_a_id) & away_wins)
        ).sum()
    )
    team_b_wins = int(
        (
            ((completed["home_club_id"] == team_b_id) & home_wins)
            | ((completed["away_club_id"] == team_b_id) & away_wins)
        ).sum()
    )
    draw_count = int(draws.sum())

    return {
        "team_a_id": team_a_id,
        "team_b_id": team_b_id,
        "played": int(played),
        "team_a_wins": team_a_wins,
        "draws": draw_count,
        "team_b_wins": team_b_wins,
        "team_a_win_rate": round(team_a_wins / played, 3),
        "draw_rate": round(draw_count / played, 3),
        "team_b_win_rate": round(team_b_wins / played, 3),
    }


def _empty_head_to_head_summary(team_a_id: int, team_b_id: int) -> dict[str, object]:
    return {
        "team_a_id": team_a_id,
        "team_b_id": team_b_id,
        "played": 0,
        "team_a_wins": 0,
        "draws": 0,
        "team_b_wins": 0,
        "team_a_win_rate": 0.0,
        "draw_rate": 0.0,
        "team_b_win_rate": 0.0,
    }


def compare_teams(matches: pd.DataFrame, team_a_id: int, team_b_id: int, last_n: int = 10) -> pd.DataFrame:
    summaries = [
        summarize_team(matches, team_a_id, last_n=last_n),
        summarize_team(matches, team_b_id, last_n=last_n),
    ]
    return pd.DataFrame(summaries)


def monthly_team_performance(matches: pd.DataFrame, team_id: int) -> pd.DataFrame:
    team_matches = filter_team_matches(matches, team_id).copy()
    if team_matches.empty:
        return pd.DataFrame(columns=["month", "played", "win_rate", "avg_goals_for", "avg_goals_against"])

    team_matches["month"] = team_matches["date"].dt.to_period("M").astype(str)
    monthly = (
        team_matches.groupby("month", as_index=False)
        .agg(
            played=("game_id", "nunique"),
            win_rate=("won", "mean"),
            avg_goals_for=("goals_for", "mean"),
            avg_goals_against=("goals_against", "mean"),
        )
        .sort_values("month")
    )
    monthly[["win_rate", "avg_goals_for", "avg_goals_against"]] = monthly[
        ["win_rate", "avg_goals_for", "avg_goals_against"]
    ].round(3)
    return monthly


def red_card_impact(matches: pd.DataFrame, team_id: int) -> pd.DataFrame:
    team_matches = filter_team_matches(matches, team_id).copy()
    if "had_red_card" not in team_matches.columns:
        team_matches["had_red_card"] = False

    impact = (
        team_matches.groupby("had_red_card", as_index=False)
        .agg(
            played=("game_id", "nunique"),
            win_rate=("won", "mean"),
            avg_goals_for=("goals_for", "mean"),
            avg_goals_against=("goals_against", "mean"),
        )
        .replace({"had_red_card": {True: "Con roja", False: "Sin roja"}})
    )
    impact[["win_rate", "avg_goals_for", "avg_goals_against"]] = impact[
        ["win_rate", "avg_goals_for", "avg_goals_against"]
    ].round(3)
    return impact


def league_competitiveness(matches: pd.DataFrame, competition_id: str | None = None, season: int | None = None) -> dict[str, object]:
    data = matches.copy()
    if competition_id:
        data = data[data["competition_id"] == competition_id]
    if season is not None:
        data = data[data["season"] == season]

    if data.empty:
        return {"teams": 0, "avg_points": 0.0, "points_std": 0.0, "points_spread": 0.0, "parity_index": 0.0}

    data["points"] = data["won"].astype(int) * 3 + data["draw"].astype(int)
    table = data.groupby("team_id", as_index=False).agg(points=("points", "sum"), played=("game_id", "nunique"))
    points_std = float(table["points"].std(ddof=0)) if len(table) else 0.0
    points_spread = float(table["points"].max() - table["points"].min()) if len(table) else 0.0
    max_possible_spread = max(float(table["played"].max() * 3), 1.0)
    parity_index = max(0.0, 1.0 - (points_std / max_possible_spread))

    return {
        "teams": int(len(table)),
        "avg_points": round(float(table["points"].mean()), 2),
        "points_std": round(points_std, 2),
        "points_spread": round(points_spread, 2),
        "parity_index": round(parity_index, 3),
    }
