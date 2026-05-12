from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata

import pandas as pd


GENERIC_TEAM_TOKENS = {
    "a",
    "ac",
    "afc",
    "as",
    "ca",
    "cd",
    "cf",
    "club",
    "de",
    "fc",
    "fk",
    "if",
    "real",
    "sc",
    "sd",
    "sk",
    "the",
}


@dataclass(frozen=True)
class TeamNameMatch:
    team_id: int
    team_name: str
    score: float


def build_team_name_index(games: pd.DataFrame) -> pd.DataFrame:
    home = games[["home_club_id", "home_club_name"]].rename(
        columns={"home_club_id": "team_id", "home_club_name": "team_name"}
    )
    away = games[["away_club_id", "away_club_name"]].rename(
        columns={"away_club_id": "team_id", "away_club_name": "team_name"}
    )
    teams = pd.concat([home, away], ignore_index=True).dropna().drop_duplicates()
    teams["normalized_name"] = teams["team_name"].map(normalize_team_name)
    return teams[teams["normalized_name"] != ""].sort_values("team_name").reset_index(drop=True)


def find_best_team_match(
    external_team_name: str,
    team_index: pd.DataFrame,
    min_score: float = 0.78,
) -> TeamNameMatch | None:
    normalized_external = normalize_team_name(external_team_name)
    if not normalized_external or team_index.empty:
        return None

    exact = team_index[team_index["normalized_name"] == normalized_external]
    if not exact.empty:
        row = exact.iloc[0]
        return TeamNameMatch(team_id=int(row["team_id"]), team_name=str(row["team_name"]), score=1.0)

    best_match: TeamNameMatch | None = None
    for row in team_index.itertuples():
        score = SequenceMatcher(None, normalized_external, row.normalized_name).ratio()
        if best_match is None or score > best_match.score:
            best_match = TeamNameMatch(team_id=int(row.team_id), team_name=str(row.team_name), score=round(score, 3))

    if best_match is None or best_match.score < min_score:
        return None
    return best_match


def normalize_team_name(value: object) -> str:
    if value is None:
        return ""

    text = str(value).lower().strip()
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    tokens = [token for token in text.split() if token not in GENERIC_TEAM_TOKENS]
    return " ".join(tokens)
