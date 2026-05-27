from __future__ import annotations

import argparse
import sys

import pandas as pd

from sports_analytics.config import API_FOOTBALL_FIXTURES_RAW_DIR, API_FOOTBALL_PARQUET_DIR
from sports_analytics.ingestion.api_football_fixtures import (
    append_request_log,
    build_fixture_quality_report,
    load_raw_fixture_payload,
    normalize_fixture_payload,
    save_quality_report,
    save_raw_fixture_payload,
    utc_now_iso,
    write_fixtures_parquet,
)
from sports_analytics.services.api_football import ApiFootballError, fetch_fixtures_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingiere fixtures desde API-Football por liga/temporada.")
    parser.add_argument("--league", required=True, help="League ID o lista separada por coma, ejemplo: 128,39,140.")
    parser.add_argument("--season", type=int, required=True, help="Temporada de API-Football.")
    parser.add_argument("--next", dest="next_count", type=int, help="Cantidad de proximos fixtures a pedir.")
    parser.add_argument("--from-date", help="Fecha desde, formato YYYY-MM-DD.")
    parser.add_argument("--to-date", help="Fecha hasta, formato YYYY-MM-DD.")
    parser.add_argument("--team", type=int, help="Team ID opcional. Usarlo solo si hace falta.")
    parser.add_argument("--allow-quality-errors", action="store_true", help="Guarda artefactos aunque haya errores de calidad.")
    args = parser.parse_args()

    try:
        raw_paths = []
        frames = []
        for league_id in _parse_league_ids(args.league):
            response = fetch_fixtures_payload(
                league_id=league_id,
                season=args.season,
                team_id=args.team,
                next_count=args.next_count,
                from_date=args.from_date,
                to_date=args.to_date,
            )
            ingested_at = utc_now_iso()
            raw_path = save_raw_fixture_payload(response, raw_dir=API_FOOTBALL_FIXTURES_RAW_DIR, ingested_at=ingested_at)
            raw_paths.append(raw_path)
            raw_content = load_raw_fixture_payload(raw_path)
            frame = normalize_fixture_payload(raw_content)
            frames.append(frame)
            rows = len(frame)
            append_request_log(response, raw_path, rows, requested_at=ingested_at)

        fixtures = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        quality_report = build_fixture_quality_report(fixtures)
        quality_report_path = save_quality_report(quality_report, None, args.season)
        error_count = int((quality_report["severity"] == "error").sum()) if not quality_report.empty else 0
        warning_count = int((quality_report["severity"] == "warning").sum()) if not quality_report.empty else 0
        if error_count and not args.allow_quality_errors:
            print(f"La ingesta de fixtures tiene {error_count} errores de calidad. Ver {quality_report_path}.")
            return 1
        parquet_path = write_fixtures_parquet(fixtures, output_dir=API_FOOTBALL_PARQUET_DIR)
    except ApiFootballError as exc:
        print(f"Error consultando API-Football: {exc}")
        return 1
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Fixtures procesados: {len(fixtures)}")
    print("Raw JSON:")
    for raw_path in raw_paths:
        print(f"- {raw_path}")
    print(f"Parquet: {parquet_path}")
    print(f"Reporte de calidad: {quality_report_path}")
    print(f"Errores: {error_count} | Warnings: {warning_count}")
    return 0


def _parse_league_ids(raw_value: str) -> list[int]:
    return [int(part.strip()) for part in raw_value.replace(";", ",").split(",") if part.strip()]


if __name__ == "__main__":
    sys.exit(main())
