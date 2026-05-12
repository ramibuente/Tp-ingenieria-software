from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sports_analytics.config import RAW_DIR
from sports_analytics.data_catalog import TABLES
from sports_analytics.etl.quality import build_quality_report


@dataclass(frozen=True)
class ValidationResult:
    table: str
    ok: bool
    message: str
    errors: int = 0
    warnings: int = 0


def validate_table(table_name: str, raw_dir: Path = RAW_DIR, sample_rows: int = 50_000) -> ValidationResult:
    spec = TABLES[table_name]
    csv_path = raw_dir / spec.file_name

    if not csv_path.exists():
        return ValidationResult(table_name, False, f"No existe {csv_path}", errors=1)

    try:
        found_columns = tuple(pd.read_csv(csv_path, nrows=0).columns)
    except Exception as exc:
        return ValidationResult(table_name, False, f"No se pudo leer: {exc}", errors=1)

    expected_columns = spec.columns
    missing = [col for col in expected_columns if col not in found_columns]
    extra = [col for col in found_columns if col not in expected_columns]

    if missing:
        return ValidationResult(table_name, False, f"Faltan columnas: {missing}", errors=len(missing))

    try:
        sample = pd.read_csv(csv_path, nrows=sample_rows, low_memory=False)
        quality_report = build_quality_report(table_name, sample)
    except Exception as exc:
        return ValidationResult(table_name, False, f"No se pudo evaluar la calidad de datos: {exc}", errors=1)

    errors = int((quality_report["severity"] == "error").sum()) if not quality_report.empty else 0
    warnings = int((quality_report["severity"] == "warning").sum()) if not quality_report.empty else 0

    detail = "OK"
    if extra:
        detail = f"OK con columnas extra: {extra}"
    if warnings:
        detail = f"{detail}. Advertencias de calidad: {warnings}"

    return ValidationResult(table_name, errors == 0, detail, errors=errors, warnings=warnings)


def validate_all(raw_dir: Path = RAW_DIR, sample_rows: int = 50_000) -> list[ValidationResult]:
    return [validate_table(table_name, raw_dir, sample_rows=sample_rows) for table_name in TABLES]
