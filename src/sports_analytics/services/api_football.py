from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import requests

from sports_analytics.config import PROJECT_ROOT


API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_KEY_ENV_VARS = ("APIFOOTBALL_API_KEY", "API_FOOTBALL_KEY", "APISPORTS_KEY")


class ApiFootballError(RuntimeError):
    """Error recuperable al consultar API-Football."""


class ApiFootballConfigError(ApiFootballError):
    """Falta configuracion local para consultar API-Football."""


@dataclass(frozen=True)
class ApiFootballRawResponse:
    payload: dict[str, Any]
    endpoint: str
    params: dict[str, Any]
    status_code: int
    remaining_requests: int | None
    daily_limit: int | None


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


@dataclass(frozen=True)
class LiveFixture:
    fixture_id: int | None
    date: str
    elapsed: int | None
    status: str
    league_id: int | None
    league_name: str
    season: int | None
    round_name: str
    home_team_id: int | None
    home_team: str
    away_team_id: int | None
    away_team: str
    goals_home: int | None
    goals_away: int | None


def get_api_football_key() -> str | None:
    for env_var in API_KEY_ENV_VARS:
        value = os.getenv(env_var)
        if value:
            return value.strip()
    return _get_api_key_from_dotenv()


def _get_api_key_from_dotenv(dotenv_path: Path = PROJECT_ROOT / ".env") -> str | None:
    if not dotenv_path.exists():
        return None

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() in API_KEY_ENV_VARS and value.strip():
            return value.strip().strip('"').strip("'")
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
    raw_response = fetch_fixtures_payload(
        next_count=next_count,
        league_id=league_id,
        season=season,
        team_id=team_id,
        timezone=timezone,
        api_key=api_key,
        timeout=timeout,
    )
    return parse_upcoming_fixtures(raw_response.payload, limit=next_count)


def fetch_fixtures_payload(
    *,
    league_id: int | None = None,
    season: int | None = None,
    team_id: int | None = None,
    next_count: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    timezone: str = "America/Argentina/Buenos_Aires",
    api_key: str | None = None,
    timeout: int = 15,
) -> ApiFootballRawResponse:
    """Consulta /fixtures y devuelve el JSON crudo con metadatos de cuota.

    La ingesta recomendada para el proyecto es por liga + temporada, porque
    reduce requests frente a pedir un equipo por vez.
    """
    resolved_key = api_key or get_api_football_key()
    if not resolved_key:
        env_names = ", ".join(API_KEY_ENV_VARS)
        raise ApiFootballConfigError(f"Falta configurar una API key en alguna de estas variables: {env_names}.")

    params: dict[str, Any] = {
        "timezone": timezone,
    }
    if next_count is not None:
        params["next"] = max(1, min(int(next_count), 100))
    if league_id is not None:
        params["league"] = int(league_id)
    if season is not None:
        params["season"] = int(season)
    if team_id is not None:
        params["team"] = int(team_id)
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

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

    return ApiFootballRawResponse(
        payload=payload,
        endpoint="/fixtures",
        params=params,
        status_code=response.status_code,
        remaining_requests=_first_int_header(
            response.headers,
            "x-ratelimit-requests-remaining",
            "X-Ratelimit-Remaining",
        ),
        daily_limit=_first_int_header(
            response.headers,
            "x-ratelimit-requests-limit",
            "X-Ratelimit-Limit",
        ),
    )


def parse_upcoming_fixtures(payload: dict[str, Any], limit: int | None = None) -> list[UpcomingFixture]:
    fixtures = payload.get("response", [])
    if not isinstance(fixtures, list):
        raise ApiFootballError("API-Football devolvio un formato inesperado en el campo response.")

    selected = fixtures if limit is None else fixtures[:limit]
    return [_parse_fixture(item) for item in selected]


def fetch_live_fixtures(
    league_id: int | None = None,
    timezone: str = "America/Argentina/Buenos_Aires",
    api_key: str | None = None,
    timeout: int = 15,
) -> list[LiveFixture]:
    resolved_key = api_key or get_api_football_key()
    if not resolved_key:
        env_names = ", ".join(API_KEY_ENV_VARS)
        raise ApiFootballConfigError(f"Falta configurar una API key en alguna de estas variables: {env_names}.")

    params: dict[str, Any] = {"live": "all", "timezone": timezone}
    if league_id is not None:
        params["league"] = int(league_id)

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
        return []
    return [_parse_live_fixture(item) for item in fixtures]


def fetch_fixture_events(
    fixture_id: int,
    api_key: str | None = None,
    timeout: int = 15,
) -> ApiFootballRawResponse:
    resolved_key = api_key or get_api_football_key()
    if not resolved_key:
        env_names = ", ".join(API_KEY_ENV_VARS)
        raise ApiFootballConfigError(f"Falta configurar una API key en alguna de estas variables: {env_names}.")

    params: dict[str, Any] = {"fixture": int(fixture_id)}

    try:
        response = requests.get(
            f"{API_FOOTBALL_BASE_URL}/fixtures/events",
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

    return ApiFootballRawResponse(
        payload=payload,
        endpoint="/fixtures/events",
        params=params,
        status_code=response.status_code,
        remaining_requests=_first_int_header(response.headers, "x-ratelimit-requests-remaining", "X-Ratelimit-Remaining"),
        daily_limit=_first_int_header(response.headers, "x-ratelimit-requests-limit", "X-Ratelimit-Limit"),
    )


def _parse_live_fixture(item: dict[str, Any]) -> LiveFixture:
    fixture = item.get("fixture") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    status = fixture.get("status") or {}
    goals = item.get("goals") or {}

    return LiveFixture(
        fixture_id=_to_int_or_none(fixture.get("id")),
        date=str(fixture.get("date") or ""),
        elapsed=_to_int_or_none(status.get("elapsed")),
        status=str(status.get("long") or status.get("short") or ""),
        league_id=_to_int_or_none(league.get("id")),
        league_name=str(league.get("name") or ""),
        season=_to_int_or_none(league.get("season")),
        round_name=str(league.get("round") or ""),
        home_team_id=_to_int_or_none(home.get("id")),
        home_team=str(home.get("name") or ""),
        away_team_id=_to_int_or_none(away.get("id")),
        away_team=str(away.get("name") or ""),
        goals_home=_to_int_or_none(goals.get("home")),
        goals_away=_to_int_or_none(goals.get("away")),
    )


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


def _first_int_header(headers: requests.structures.CaseInsensitiveDict[str], *names: str) -> int | None:
    for name in names:
        value = headers.get(name)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None
