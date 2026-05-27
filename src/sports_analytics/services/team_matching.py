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
    "asociacion",
    "association",
    "atletica",
    "atletico",
    "ca",
    "cd",
    "cf",
    "club",
    "central",
    "de",
    "del",
    "fc",
    "fk",
    "if",
    "real",
    "s",
    "sc",
    "sd",
    "sk",
    "the",
}

TOKEN_ALIASES = {
    "jrs": "juniors",
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
        score = _name_similarity(normalized_external, row.normalized_name)
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
    tokens = [_normalize_token(TOKEN_ALIASES.get(token, token)) for token in text.split()]
    tokens = [token for token in tokens if token and token not in GENERIC_TEAM_TOKENS]
    return " ".join(tokens)


def _normalize_token(token: str) -> str:
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def _name_similarity(left: str, right: str) -> float:
    sequence_score = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return sequence_score

    overlap = left_tokens & right_tokens
    union = left_tokens | right_tokens
    jaccard_score = len(overlap) / len(union)
    containment_score = len(overlap) / min(len(left_tokens), len(right_tokens))

    if containment_score == 1 and len(overlap) >= 1:
        containment_score = max(containment_score, 0.86)

    return max(sequence_score, jaccard_score, containment_score)
