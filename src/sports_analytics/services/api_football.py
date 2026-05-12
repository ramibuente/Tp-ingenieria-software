from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import requests


API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_KEY_ENV_VARS = ("APIFOOTBALL_API_KEY", "API_FOOTBALL_KEY", "APISPORTS_KEY")


class ApiFootballError(RuntimeError):
    """Error recuperable al consultar API-Football."""


class ApiFootballConfigError(ApiFootballError):
    """Falta configuracion local para consultar API-Football."""


@dataclass(frozen=True)
class UpcomingFixture:
    fixture_id: int | None
    date: str
    status: str
    league_id: int | None
    league_name: str
    season: int | None
    round_name: str
    home_team_id: int | None
    home_team: str
    away_team_id: int | None
    away_team: str


def get_api_football_key() -> str | None:
    for env_var in API_KEY_ENV_VARS:
        value = os.getenv(env_var)
        if value:
            return value.strip()
    return None


def fetch_upcoming_fixtures(
    next_count: int = 5,
    league_id: int | None = None,
    season: int | None = None,
    team_id: int | None = None,
    timezone: str = "America/Argentina/Buenos_Aires",
    api_key: str | None = None,
    timeout: int = 15,
) -> list[UpcomingFixture]:
    resolved_key = api_key or get_api_football_key()
    if not resolved_key:
        env_names = ", ".join(API_KEY_ENV_VARS)
        raise ApiFootballConfigError(f"Falta configurar una API key en alguna de estas variables: {env_names}.")

    params: dict[str, Any] = {
        "next": max(1, min(int(next_count), 20)),
        "timezone": timezone,
    }
    if league_id is not None:
        params["league"] = int(league_id)
    if season is not None:
        params["season"] = int(season)
    if team_id is not None:
        params["team"] = int(team_id)

    try:
        response = requests.get(
            f"{API_FOOTBALL_BASE_URL}/fixtures",
            headers={"x-apisports-key": resolved_key, "Accept": "application/json"},
            params=params,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise ApiFootballError(f"No se pudo conectar con API-Football. Detalle: {exc}") from exc
    except ValueError as exc:
        raise ApiFootballError("API-Football devolvio una respuesta que no es JSON valido.") from exc

    errors = payload.get("errors")
    if errors:
        raise ApiFootballError(f"API-Football informo un error: {_format_api_errors(errors)}")

    fixtures = payload.get("response", [])
    if not isinstance(fixtures, list):
        raise ApiFootballError("API-Football devolvio un formato inesperado en el campo response.")

    return [_parse_fixture(item) for item in fixtures[:next_count]]


def _parse_fixture(item: dict[str, Any]) -> UpcomingFixture:
    fixture = item.get("fixture") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    status = fixture.get("status") or {}

    return UpcomingFixture(
        fixture_id=_to_int_or_none(fixture.get("id")),
        date=str(fixture.get("date") or ""),
        status=str(status.get("long") or status.get("short") or ""),
        league_id=_to_int_or_none(league.get("id")),
        league_name=str(league.get("name") or ""),
        season=_to_int_or_none(league.get("season")),
        round_name=str(league.get("round") or ""),
        home_team_id=_to_int_or_none(home.get("id")),
        home_team=str(home.get("name") or ""),
        away_team_id=_to_int_or_none(away.get("id")),
        away_team=str(away.get("name") or ""),
    )


def _format_api_errors(errors: object) -> str:
    if isinstance(errors, dict):
        return "; ".join(str(value) for value in errors.values()) or str(errors)
    if isinstance(errors, list):
        return "; ".join(str(value) for value in errors) or str(errors)
    return str(errors)


def _to_int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
