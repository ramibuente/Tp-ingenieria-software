from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from sports_analytics.config import (
    API_FOOTBALL_EVENTS_PARQUET_DIR,
    API_FOOTBALL_EVENTS_RAW_DIR,
    API_FOOTBALL_FIXTURES_RAW_DIR,
    API_FOOTBALL_PARQUET_DIR,
    QUALITY_REPORTS_DIR,
    REQUEST_LOG_DIR,
)

if TYPE_CHECKING:
    from sports_analytics.services.api_football import ApiFootballRawResponse


FIXTURE_COLUMNS = [
    "fixture_id",
    "fixture_date",
    "fixture_timestamp",
    "timezone",
    "status_short",
    "status_long",
    "league_id",
    "league_name",
    "season",
    "round_name",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "venue_name",
    "venue_city",
    "goals_home",
    "goals_away",
    "score_ht_home",
    "score_ht_away",
    "score_ft_home",
    "score_ft_away",
    "source_endpoint",
    "source_params",
    "ingested_at",
]

FIXTURE_EVENTS_COLUMNS = [
    "fixture_id",
    "elapsed",
    "elapsed_extra",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    "assist_id",
    "assist_name",
    "event_type",
    "event_detail",
    "ingested_at",
]


@dataclass(frozen=True)
class IngestionArtifacts:
    raw_path: Path
    parquet_path: Path
    quality_report_path: Path
    request_log_path: Path
    rows: int
    errors: int
    warnings: int


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def save_raw_fixture_payload(
    response: ApiFootballRawResponse,
    raw_dir: Path = API_FOOTBALL_FIXTURES_RAW_DIR,
    ingested_at: str | None = None,
) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _file_timestamp(ingested_at)
    league = response.params.get("league", "all")
    season = response.params.get("season", "all")
    path = raw_dir / f"fixtures_league-{league}_season-{season}_{timestamp}.json"
    content = {
        "ingested_at": ingested_at or utc_now_iso(),
        "endpoint": response.endpoint,
        "params": response.params,
        "status_code": response.status_code,
        "remaining_requests": response.remaining_requests,
        "daily_limit": response.daily_limit,
        "payload": response.payload,
    }
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_raw_fixture_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_raw_fixture_payload(raw_dir: Path = API_FOOTBALL_FIXTURES_RAW_DIR) -> Path | None:
    files = sorted(raw_dir.glob("fixtures_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def normalize_fixture_payload(raw_content: dict[str, Any]) -> pd.DataFrame:
    payload = raw_content.get("payload", raw_content)
    response = payload.get("response", [])
    if not isinstance(response, list):
        return pd.DataFrame(columns=FIXTURE_COLUMNS)

    ingested_at = raw_content.get("ingested_at") or utc_now_iso()
    endpoint = str(raw_content.get("endpoint") or "/fixtures")
    params = raw_content.get("params") or {}
    params_json = json.dumps(params, ensure_ascii=False, sort_keys=True)

    records = []
    for item in response:
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        status = fixture.get("status") or {}
        venue = fixture.get("venue") or {}
        goals = item.get("goals") or {}

        score = item.get("score") or {}
        ht = score.get("halftime") or {}
        ft = score.get("fulltime") or {}

        records.append(
            {
                "fixture_id": _to_int_or_none(fixture.get("id")),
                "fixture_date": pd.to_datetime(fixture.get("date"), errors="coerce", utc=True),
                "fixture_timestamp": _to_int_or_none(fixture.get("timestamp")),
                "timezone": fixture.get("timezone"),
                "status_short": status.get("short"),
                "status_long": status.get("long"),
                "league_id": _to_int_or_none(league.get("id")),
                "league_name": _clean_text(league.get("name")),
                "season": _to_int_or_none(league.get("season")),
                "round_name": _clean_text(league.get("round")),
                "home_team_id": _to_int_or_none(home.get("id")),
                "home_team_name": _clean_text(home.get("name")),
                "away_team_id": _to_int_or_none(away.get("id")),
                "away_team_name": _clean_text(away.get("name")),
                "venue_name": _clean_text(venue.get("name")),
                "venue_city": _clean_text(venue.get("city")),
                "goals_home": _to_int_or_none(goals.get("home")),
                "goals_away": _to_int_or_none(goals.get("away")),
                "score_ht_home": _to_int_or_none(ht.get("home")),
                "score_ht_away": _to_int_or_none(ht.get("away")),
                "score_ft_home": _to_int_or_none(ft.get("home")),
                "score_ft_away": _to_int_or_none(ft.get("away")),
                "source_endpoint": endpoint,
                "source_params": params_json,
                "ingested_at": pd.to_datetime(ingested_at, errors="coerce", utc=True),
            }
        )

    frame = pd.DataFrame(records, columns=FIXTURE_COLUMNS)
    for column in ["fixture_id", "fixture_timestamp", "league_id", "season", "home_team_id", "away_team_id", "goals_home", "goals_away", "score_ht_home", "score_ht_away", "score_ft_home", "score_ft_away"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def build_fixture_quality_report(fixtures: pd.DataFrame) -> pd.DataFrame:
    issues: list[dict[str, object]] = []
    required_columns = ["fixture_id", "fixture_date", "league_id", "season", "home_team_name", "away_team_name"]
    for column in required_columns:
        if column not in fixtures.columns:
            issues.append(_issue("error", "missing_column", column, 1, f"Falta la columna obligatoria '{column}'."))

    if issues:
        return pd.DataFrame(issues)

    for column in required_columns:
        null_count = int(fixtures[column].isna().sum())
        if null_count:
            issues.append(_issue("error", "null_required_value", column, null_count, f"La columna '{column}' tiene valores vacios."))

    duplicate_count = int(fixtures["fixture_id"].duplicated().sum()) if "fixture_id" in fixtures.columns else 0
    if duplicate_count:
        issues.append(_issue("error", "duplicated_fixture_id", "fixture_id", duplicate_count, "Hay fixtures duplicados por fixture_id."))

    same_team_count = int((fixtures["home_team_id"] == fixtures["away_team_id"]).sum()) if {"home_team_id", "away_team_id"}.issubset(fixtures.columns) else 0
    if same_team_count:
        issues.append(_issue("error", "same_home_away_team", "home_team_id/away_team_id", same_team_count, "Hay fixtures donde local y visitante son el mismo equipo."))

    missing_status = int(fixtures["status_short"].isna().sum()) if "status_short" in fixtures.columns else 0
    if missing_status:
        issues.append(_issue("warning", "missing_status", "status_short", missing_status, "Hay fixtures sin estado informado por la API."))

    return pd.DataFrame(issues, columns=["severity", "issue", "column", "count", "message"])


def write_fixtures_parquet(fixtures: pd.DataFrame, output_dir: Path = API_FOOTBALL_PARQUET_DIR, overwrite: bool = True) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "fixtures.parquet"
    if overwrite and output_file.exists():
        output_file.unlink()
    fixtures.to_parquet(output_file, index=False)
    return output_file


def load_processed_fixtures(parquet_dir: Path = API_FOOTBALL_PARQUET_DIR) -> pd.DataFrame:
    parquet_file = parquet_dir / "fixtures.parquet"
    if not parquet_file.exists():
        return pd.DataFrame(columns=FIXTURE_COLUMNS)
    return pd.read_parquet(parquet_file)


def save_quality_report(report: pd.DataFrame, league_id: int | None, season: int | None, output_dir: Path = QUALITY_REPORTS_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"api_football_fixtures_league-{league_id or 'all'}_season-{season or 'all'}.csv"
    report.to_csv(path, index=False)
    return path


def append_request_log(
    response: ApiFootballRawResponse,
    raw_path: Path,
    rows: int,
    output_dir: Path = REQUEST_LOG_DIR,
    requested_at: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "api_football_requests.csv"
    entry = pd.DataFrame(
        [
            {
                "requested_at": requested_at or utc_now_iso(),
                "source_system": "api-football",
                "endpoint": response.endpoint,
                "params": json.dumps(response.params, ensure_ascii=False, sort_keys=True),
                "status_code": response.status_code,
                "rows": rows,
                "remaining_requests": response.remaining_requests,
                "daily_limit": response.daily_limit,
                "raw_path": str(raw_path),
            }
        ]
    )
    entry.to_csv(path, mode="a", header=not path.exists(), index=False)
    return path


def build_artifacts_from_response(
    response: ApiFootballRawResponse,
    *,
    raw_dir: Path = API_FOOTBALL_FIXTURES_RAW_DIR,
    parquet_dir: Path = API_FOOTBALL_PARQUET_DIR,
    fail_on_quality_errors: bool = True,
) -> IngestionArtifacts:
    ingested_at = utc_now_iso()
    raw_path = save_raw_fixture_payload(response, raw_dir=raw_dir, ingested_at=ingested_at)
    raw_content = load_raw_fixture_payload(raw_path)
    fixtures = normalize_fixture_payload(raw_content)
    quality_report = build_fixture_quality_report(fixtures)
    quality_report_path = save_quality_report(
        quality_report,
        response.params.get("league"),
        response.params.get("season"),
    )
    error_count = int((quality_report["severity"] == "error").sum()) if not quality_report.empty else 0
    warning_count = int((quality_report["severity"] == "warning").sum()) if not quality_report.empty else 0
    if fail_on_quality_errors and error_count:
        raise ValueError(f"La ingesta de fixtures tiene {error_count} errores de calidad. Ver {quality_report_path}.")
    parquet_path = write_fixtures_parquet(fixtures, output_dir=parquet_dir)
    request_log_path = append_request_log(response, raw_path, len(fixtures), requested_at=ingested_at)
    return IngestionArtifacts(
        raw_path=raw_path,
        parquet_path=parquet_path,
        quality_report_path=quality_report_path,
        request_log_path=request_log_path,
        rows=len(fixtures),
        errors=error_count,
        warnings=warning_count,
    )


def normalize_fixture_events_payload(fixture_id: int, raw_response: "ApiFootballRawResponse") -> pd.DataFrame:
    events = raw_response.payload.get("response", [])
    if not isinstance(events, list):
        return pd.DataFrame(columns=FIXTURE_EVENTS_COLUMNS)

    ingested_at = pd.to_datetime(utc_now_iso(), errors="coerce", utc=True)
    records = []
    for event in events:
        time = event.get("time") or {}
        team = event.get("team") or {}
        player = event.get("player") or {}
        assist = event.get("assist") or {}
        records.append(
            {
                "fixture_id": int(fixture_id),
                "elapsed": _to_int_or_none(time.get("elapsed")),
                "elapsed_extra": _to_int_or_none(time.get("extra")),
                "team_id": _to_int_or_none(team.get("id")),
                "team_name": _clean_text(team.get("name")),
                "player_id": _to_int_or_none(player.get("id")),
                "player_name": _clean_text(player.get("name")),
                "assist_id": _to_int_or_none(assist.get("id")),
                "assist_name": _clean_text(assist.get("name")),
                "event_type": _clean_text(event.get("type")),
                "event_detail": _clean_text(event.get("detail")),
                "ingested_at": ingested_at,
            }
        )

    return pd.DataFrame(records, columns=FIXTURE_EVENTS_COLUMNS)


def write_events_parquet(events: pd.DataFrame, fixture_id: int, output_dir: Path = API_FOOTBALL_EVENTS_PARQUET_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"events_fixture_{fixture_id}.parquet"
    events.to_parquet(path, index=False)
    return path


def load_processed_events(fixture_id: int, parquet_dir: Path = API_FOOTBALL_EVENTS_PARQUET_DIR) -> pd.DataFrame:
    path = parquet_dir / f"events_fixture_{fixture_id}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=FIXTURE_EVENTS_COLUMNS)
    return pd.read_parquet(path)


def load_all_processed_events(parquet_dir: Path = API_FOOTBALL_EVENTS_PARQUET_DIR) -> pd.DataFrame:
    if not parquet_dir.exists():
        return pd.DataFrame(columns=FIXTURE_EVENTS_COLUMNS)
    files = sorted(parquet_dir.glob("events_fixture_*.parquet"))
    if not files:
        return pd.DataFrame(columns=FIXTURE_EVENTS_COLUMNS)
    frames = [pd.read_parquet(f) for f in files]
    return pd.concat(frames, ignore_index=True)


def save_raw_events_payload(
    fixture_id: int,
    response: "ApiFootballRawResponse",
    raw_dir: Path = API_FOOTBALL_EVENTS_RAW_DIR,
    ingested_at: str | None = None,
) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _file_timestamp(ingested_at)
    path = raw_dir / f"events_fixture_{fixture_id}_{timestamp}.json"
    content = {
        "ingested_at": ingested_at or utc_now_iso(),
        "fixture_id": fixture_id,
        "endpoint": response.endpoint,
        "params": response.params,
        "status_code": response.status_code,
        "remaining_requests": response.remaining_requests,
        "daily_limit": response.daily_limit,
        "payload": response.payload,
    }
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _issue(severity: str, issue: str, column: str, count: int, message: str) -> dict[str, object]:
    return {
        "severity": severity,
        "issue": issue,
        "column": column,
        "count": count,
        "message": message,
    }


def _file_timestamp(value: str | None) -> str:
    raw = value or utc_now_iso()
    return raw.replace(":", "").replace("-", "").replace("+", "Z")


def _to_int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None
