from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

import pandas as pd
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
import psycopg2

AIRFLOW_HOME = Path(os.getenv("AIRFLOW_HOME", "/opt/airflow"))
SRC_DIR = AIRFLOW_HOME / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sports_analytics.config import API_FOOTBALL_MAX_SEASON, CURRENT_DATE, CURRENT_SEASON  # noqa: E402
from sports_analytics.ingestion.api_football_fixtures import (  # noqa: E402
    append_request_log,
    build_fixture_quality_report,
    load_processed_fixtures,
    load_raw_fixture_payload,
    normalize_fixture_events_payload,
    normalize_fixture_payload,
    save_quality_report,
    save_raw_events_payload,
    save_raw_fixture_payload,
    utc_now_iso,
    write_events_parquet,
    write_fixtures_parquet,
)
from sports_analytics.services.api_football import fetch_fixture_events, fetch_fixtures_payload  # noqa: E402


logger = logging.getLogger(__name__)

default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
}


def _config_value(variable_name: str, env_name: str, required: bool = True) -> str | None:
    value = Variable.get(variable_name, default_var=None) or os.getenv(env_name)
    if required and not value:
        raise ValueError(f"Falta configurar {variable_name} en Airflow Variables o {env_name} en el entorno.")
    return value


def _get_dwh_connection():
    raw_uri = os.getenv("AIRFLOW_CONN_POSTGRES_DWH")
    if not raw_uri:
        raise ValueError("AIRFLOW_CONN_POSTGRES_DWH no está configurado. Definilo en el entorno o en Airflow Connections.")
    parsed = urlparse(raw_uri)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
    )


def _validate_dwh(**context) -> None:
    with _get_dwh_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    logger.info("Conexion DWH OK.")


def _validate_config(**context) -> dict[str, object]:
    league_ids = _parse_league_ids()
    season_raw = _config_value("api_football_season", "API_FOOTBALL_SEASON", required=False)
    season = int(season_raw) if season_raw else CURRENT_SEASON
    if season > API_FOOTBALL_MAX_SEASON:
        raise ValueError(f"API-Football solo acepta temporadas hasta {API_FOOTBALL_MAX_SEASON}.")
    next_count_raw = _config_value("api_football_next_fixtures", "API_FOOTBALL_NEXT_FIXTURES", required=False)
    next_count = int(next_count_raw) if next_count_raw else None
    if next_count is not None and next_count < 1:
        next_count = None
    logger.info("Configuracion OK: leagues=%s season=%s next=%s", league_ids, season, next_count)
    return {"league_ids": league_ids, "season": season, "next_count": next_count}


def _parse_league_ids() -> list[int]:
    raw_value = _config_value("api_football_league_ids", "API_FOOTBALL_LEAGUE_IDS", required=False)
    if not raw_value:
        raw_value = _config_value("api_football_league_id", "API_FOOTBALL_LEAGUE_ID")

    league_ids = []
    for part in str(raw_value).replace(";", ",").split(","):
        value = part.strip()
        if value:
            league_ids.append(int(value))

    if not league_ids:
        raise ValueError("Configurar al menos una liga en API_FOOTBALL_LEAGUE_IDS o API_FOOTBALL_LEAGUE_ID.")

    return list(dict.fromkeys(league_ids))


def _fetch_api_football_fixtures(**context) -> list[str]:
    params = context["ti"].xcom_pull(task_ids="validate_config")
    raw_paths = []
    for league_id in params["league_ids"]:
        response = fetch_fixtures_payload(
            league_id=league_id,
            season=params["season"],
            next_count=params["next_count"],
        )
        raw_path = save_raw_fixture_payload(response, ingested_at=utc_now_iso())
        rows = len(response.payload.get("response", [])) if isinstance(response.payload.get("response"), list) else 0
        append_request_log(response, raw_path, rows)
        raw_paths.append(str(raw_path))

        with _get_dwh_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO etl_request_log
                    (source_system, endpoint, params, status_code, rows_loaded, remaining_requests, daily_limit, raw_path)
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                    """,
                    (
                        "api-football",
                        response.endpoint,
                        json.dumps(response.params, ensure_ascii=False, sort_keys=True),
                        response.status_code,
                        rows,
                        response.remaining_requests,
                        response.daily_limit,
                        str(raw_path),
                    ),
                )
        logger.info("Raw fixtures guardados en %s", raw_path)
    return raw_paths


def _validate_fixtures_schema(**context) -> list[str]:
    raw_paths = [Path(path) for path in context["ti"].xcom_pull(task_ids="fetch_api_football_fixtures")]
    frames = []
    for raw_path in raw_paths:
        frames.append(normalize_fixture_payload(load_raw_fixture_payload(raw_path)))

    fixtures = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    report = build_fixture_quality_report(fixtures)
    params = context["ti"].xcom_pull(task_ids="validate_config")
    report_path = save_quality_report(report, None, params["season"])
    errors = int((report["severity"] == "error").sum()) if not report.empty else 0
    if errors:
        raise ValueError(f"Calidad de fixtures fallida con {errors} errores. Ver {report_path}.")
    logger.info("Validacion OK: %s fixtures, reporte %s", len(fixtures), report_path)
    return [str(path) for path in raw_paths]


def _normalize_fixtures_to_parquet(**context) -> str:
    raw_paths = [Path(path) for path in context["ti"].xcom_pull(task_ids="validate_fixtures_schema")]
    frames = [normalize_fixture_payload(load_raw_fixture_payload(path)) for path in raw_paths]
    fixtures = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    parquet_path = write_fixtures_parquet(fixtures)
    logger.info("Fixtures normalizados en %s", parquet_path)
    return str(parquet_path)


def _load_fixtures_to_dwh(**context) -> int:
    parquet_path = Path(context["ti"].xcom_pull(task_ids="normalize_fixtures_to_parquet"))
    fixtures = pd.read_parquet(parquet_path)
    if fixtures.empty:
        logger.info("No hay fixtures para cargar.")
        return 0

    with _get_dwh_connection() as conn:
        with conn.cursor() as cur:
            for row in fixtures.to_dict(orient="records"):
                cur.execute(
                    """
                    INSERT INTO stg_api_football_fixtures (
                        fixture_id, fixture_date, fixture_timestamp, timezone, status_short, status_long,
                        league_id, league_name, season, round_name, home_team_id, home_team_name,
                        away_team_id, away_team_name, venue_name, venue_city, goals_home, goals_away,
                        score_ht_home, score_ht_away, score_ft_home, score_ft_away,
                        source_endpoint, source_params, ingested_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s::jsonb, %s
                    )
                    ON CONFLICT (fixture_id) DO UPDATE SET
                        fixture_date = EXCLUDED.fixture_date,
                        fixture_timestamp = EXCLUDED.fixture_timestamp,
                        timezone = EXCLUDED.timezone,
                        status_short = EXCLUDED.status_short,
                        status_long = EXCLUDED.status_long,
                        league_id = EXCLUDED.league_id,
                        league_name = EXCLUDED.league_name,
                        season = EXCLUDED.season,
                        round_name = EXCLUDED.round_name,
                        home_team_id = EXCLUDED.home_team_id,
                        home_team_name = EXCLUDED.home_team_name,
                        away_team_id = EXCLUDED.away_team_id,
                        away_team_name = EXCLUDED.away_team_name,
                        venue_name = EXCLUDED.venue_name,
                        venue_city = EXCLUDED.venue_city,
                        goals_home = EXCLUDED.goals_home,
                        goals_away = EXCLUDED.goals_away,
                        score_ht_home = EXCLUDED.score_ht_home,
                        score_ht_away = EXCLUDED.score_ht_away,
                        score_ft_home = EXCLUDED.score_ft_home,
                        score_ft_away = EXCLUDED.score_ft_away,
                        source_endpoint = EXCLUDED.source_endpoint,
                        source_params = EXCLUDED.source_params,
                        ingested_at = EXCLUDED.ingested_at,
                        loaded_at = CURRENT_TIMESTAMP
                    """,
                    (
                        _none_if_na(row.get("fixture_id")),
                        _none_if_na(row.get("fixture_date")),
                        _none_if_na(row.get("fixture_timestamp")),
                        _none_if_na(row.get("timezone")),
                        _none_if_na(row.get("status_short")),
                        _none_if_na(row.get("status_long")),
                        _none_if_na(row.get("league_id")),
                        _none_if_na(row.get("league_name")),
                        _none_if_na(row.get("season")),
                        _none_if_na(row.get("round_name")),
                        _none_if_na(row.get("home_team_id")),
                        _none_if_na(row.get("home_team_name")),
                        _none_if_na(row.get("away_team_id")),
                        _none_if_na(row.get("away_team_name")),
                        _none_if_na(row.get("venue_name")),
                        _none_if_na(row.get("venue_city")),
                        _none_if_na(row.get("goals_home")),
                        _none_if_na(row.get("goals_away")),
                        _none_if_na(row.get("score_ht_home")),
                        _none_if_na(row.get("score_ht_away")),
                        _none_if_na(row.get("score_ft_home")),
                        _none_if_na(row.get("score_ft_away")),
                        _none_if_na(row.get("source_endpoint")),
                        _none_if_na(row.get("source_params")) or "{}",
                        _none_if_na(row.get("ingested_at")),
                    ),
                )
    logger.info("Fixtures cargados al DWH: %s", len(fixtures))
    return len(fixtures)


def _build_fixture_marts(**context) -> None:
    with _get_dwh_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE mart_upcoming_fixtures")
            cur.execute(
                """
                INSERT INTO mart_upcoming_fixtures (
                    fixture_id, fixture_date, league_id, league_name, season, round_name,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    status_short, status_long, ingested_at
                )
                SELECT
                    fixture_id, fixture_date, league_id, league_name, season, round_name,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    status_short, status_long, ingested_at
                FROM stg_api_football_fixtures
                ORDER BY fixture_date DESC
                LIMIT 20
                """
            )
    logger.info("Mart de proximos fixtures actualizado.")


def _fetch_fixture_events(**context) -> int:
    """Trae eventos (goles, tarjetas) de fixtures terminados en los últimos 7 días.

    Limitado a MAX_EVENTS_FIXTURES requests para no superar el cupo diario del plan gratuito.
    """
    MAX_EVENTS_FIXTURES = 5
    fixtures = load_processed_fixtures()
    if fixtures.empty:
        logger.info("No hay fixtures procesados para buscar eventos.")
        return 0

    finished = fixtures[fixtures["status_short"] == "FT"].copy()
    if finished.empty:
        logger.info("No hay fixtures finalizados.")
        return 0

    finished["fixture_date"] = pd.to_datetime(finished["fixture_date"], errors="coerce", utc=True)
    cutoff = pd.Timestamp(CURRENT_DATE).tz_localize("UTC") - pd.Timedelta(days=7)
    recent = finished[finished["fixture_date"] >= cutoff].head(MAX_EVENTS_FIXTURES)

    fetched = 0
    for fixture_id in recent["fixture_id"].dropna().astype(int):
        try:
            response = fetch_fixture_events(fixture_id)
            ingested_at = utc_now_iso()
            save_raw_events_payload(fixture_id, response, ingested_at=ingested_at)
            events = normalize_fixture_events_payload(fixture_id, response)
            write_events_parquet(events, fixture_id)

            if not events.empty:
                with _get_dwh_connection() as conn:
                    with conn.cursor() as cur:
                        for row in events.to_dict(orient="records"):
                            cur.execute(
                                """
                                INSERT INTO stg_api_football_fixture_events
                                (fixture_id, elapsed, elapsed_extra, team_id, team_name,
                                 player_id, player_name, assist_id, assist_name,
                                 event_type, event_detail, ingested_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (fixture_id, elapsed, elapsed_extra, team_id, player_id, event_type, event_detail)
                                DO UPDATE SET loaded_at = CURRENT_TIMESTAMP
                                """,
                                (
                                    int(fixture_id),
                                    _none_if_na(row.get("elapsed")),
                                    _none_if_na(row.get("elapsed_extra")),
                                    _none_if_na(row.get("team_id")),
                                    _none_if_na(row.get("team_name")),
                                    _none_if_na(row.get("player_id")),
                                    _none_if_na(row.get("player_name")),
                                    _none_if_na(row.get("assist_id")),
                                    _none_if_na(row.get("assist_name")),
                                    _none_if_na(row.get("event_type")),
                                    _none_if_na(row.get("event_detail")),
                                    _none_if_na(row.get("ingested_at")),
                                ),
                            )
            fetched += 1
            logger.info("Eventos de fixture %s cargados: %s eventos.", fixture_id, len(events))
        except Exception as exc:
            logger.warning("No se pudieron obtener eventos del fixture %s: %s", fixture_id, exc)

    logger.info("Eventos descargados para %s fixtures.", fetched)
    return fetched


def _quality_check(**context) -> None:
    fixtures = load_processed_fixtures()
    report = build_fixture_quality_report(fixtures)
    errors = int((report["severity"] == "error").sum()) if not report.empty else 0

    with _get_dwh_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stg_api_football_fixtures")
            total = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM stg_api_football_fixtures WHERE fixture_date IS NULL")
            without_date = int(cur.fetchone()[0])
            cur.execute(
                """
                SELECT COUNT(*)
                FROM stg_api_football_fixtures
                WHERE home_team_name IS NULL OR away_team_name IS NULL
                """
            )
            without_teams = int(cur.fetchone()[0])
            cur.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT fixture_id
                    FROM stg_api_football_fixtures
                    GROUP BY fixture_id
                    HAVING COUNT(*) > 1
                ) duplicated
                """
            )
            duplicated = int(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO mart_fixture_quality_summary
                (fixtures_total, fixtures_without_date, fixtures_without_teams, duplicated_fixture_ids)
                VALUES (%s, %s, %s, %s)
                """,
                (total, without_date, without_teams, duplicated),
            )

    if errors or without_date or without_teams or duplicated:
        raise ValueError(
            "Quality check fallido: "
            f"errors={errors}, without_date={without_date}, without_teams={without_teams}, duplicated={duplicated}"
        )
    logger.info("Quality check OK.")


def _none_if_na(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


with DAG(
    dag_id="football_analytics_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["sports", "api-football", "etl", "dwh"],
) as dag:
    validate_dwh = PythonOperator(
        task_id="validate_dwh",
        python_callable=_validate_dwh,
    )

    validate_config = PythonOperator(
        task_id="validate_config",
        python_callable=_validate_config,
    )

    fetch_api_football_fixtures = PythonOperator(
        task_id="fetch_api_football_fixtures",
        python_callable=_fetch_api_football_fixtures,
    )

    validate_fixtures_schema = PythonOperator(
        task_id="validate_fixtures_schema",
        python_callable=_validate_fixtures_schema,
    )

    normalize_fixtures_to_parquet = PythonOperator(
        task_id="normalize_fixtures_to_parquet",
        python_callable=_normalize_fixtures_to_parquet,
    )

    load_fixtures_to_dwh = PythonOperator(
        task_id="load_fixtures_to_dwh",
        python_callable=_load_fixtures_to_dwh,
    )

    build_fixture_marts = PythonOperator(
        task_id="build_fixture_marts",
        python_callable=_build_fixture_marts,
    )

    fetch_fixture_events_task = PythonOperator(
        task_id="fetch_fixture_events",
        python_callable=_fetch_fixture_events,
    )

    quality_check = PythonOperator(
        task_id="quality_check",
        python_callable=_quality_check,
    )

    [validate_dwh, validate_config] >> fetch_api_football_fixtures
    fetch_api_football_fixtures >> validate_fixtures_schema >> normalize_fixtures_to_parquet
    normalize_fixtures_to_parquet >> load_fixtures_to_dwh >> build_fixture_marts
    build_fixture_marts >> fetch_fixture_events_task >> quality_check
