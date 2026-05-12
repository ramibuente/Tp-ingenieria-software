from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from sports_analytics.data_catalog import TABLES


@dataclass(frozen=True)
class QualityIssue:
    table: str
    severity: str
    issue: str
    column: str
    count: int
    message: str


def build_quality_report(table_name: str, dataframe: pd.DataFrame) -> pd.DataFrame:
    spec = TABLES[table_name]
    issues: list[QualityIssue] = []

    missing_columns = [column for column in spec.columns if column not in dataframe.columns]
    for column in missing_columns:
        issues.append(
            QualityIssue(
                table_name,
                "error",
                "missing_column",
                column,
                1,
                f"Falta la columna obligatoria '{column}'.",
            )
        )

    if missing_columns:
        return _issues_to_frame(issues)

    null_counts = dataframe[list(spec.columns)].isna().sum()
    for column, count in null_counts.items():
        if count > 0:
            issues.append(
                QualityIssue(
                    table_name,
                    "warning",
                    "null_values",
                    column,
                    int(count),
                    f"La columna '{column}' tiene {int(count)} valores vacios.",
                )
            )

    duplicate_rows = int(dataframe.duplicated().sum())
    if duplicate_rows > 0:
        issues.append(
            QualityIssue(
                table_name,
                "warning",
                "duplicated_rows",
                "*",
                duplicate_rows,
                f"Hay {duplicate_rows} filas completamente duplicadas.",
            )
        )

    if spec.primary_key and spec.primary_key in dataframe.columns:
        duplicate_key_count = int(dataframe[spec.primary_key].duplicated().sum())
        if duplicate_key_count > 0:
            issues.append(
                QualityIssue(
                    table_name,
                    "error",
                    "duplicated_primary_key",
                    spec.primary_key,
                    duplicate_key_count,
                    f"La clave primaria '{spec.primary_key}' aparece duplicada {duplicate_key_count} veces.",
                )
            )

    issues.extend(_domain_checks(table_name, dataframe))
    return _issues_to_frame(issues)


def build_quality_summary(table_name: str, dataframe: pd.DataFrame) -> dict[str, object]:
    report = build_quality_report(table_name, dataframe)
    return {
        "table": table_name,
        "rows": len(dataframe),
        "columns": len(dataframe.columns),
        "errors": int((report["severity"] == "error").sum()) if not report.empty else 0,
        "warnings": int((report["severity"] == "warning").sum()) if not report.empty else 0,
    }


def _domain_checks(table_name: str, dataframe: pd.DataFrame) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    if table_name == "games":
        issues.extend(_negative_values(table_name, dataframe, ["home_club_goals", "away_club_goals"]))
        if {"home_club_id", "away_club_id"}.issubset(dataframe.columns):
            same_team = int((dataframe["home_club_id"] == dataframe["away_club_id"]).sum())
            if same_team > 0:
                issues.append(
                    QualityIssue(
                        table_name,
                        "error",
                        "same_home_away_team",
                        "home_club_id/away_club_id",
                        same_team,
                        "Hay partidos donde el equipo local y visitante tienen el mismo identificador.",
                    )
                )

    if table_name == "appearances":
        issues.extend(_negative_values(table_name, dataframe, ["yellow_cards", "red_cards", "goals", "assists", "minutes_played"]))
        if "minutes_played" in dataframe.columns:
            invalid_minutes = int((dataframe["minutes_played"] > 130).sum())
            if invalid_minutes > 0:
                issues.append(
                    QualityIssue(
                        table_name,
                        "warning",
                        "minutes_out_of_range",
                        "minutes_played",
                        invalid_minutes,
                        "Hay apariciones con mas de 130 minutos; se normalizan al preparar los datos.",
                    )
                )

    if table_name == "game_lineups" and "type" in dataframe.columns:
        valid_types = {"starting_lineup", "substitutes"}
        invalid_types = int((~dataframe["type"].isin(valid_types) & dataframe["type"].notna()).sum())
        if invalid_types > 0:
            issues.append(
                QualityIssue(
                    table_name,
                    "warning",
                    "invalid_lineup_type",
                    "type",
                    invalid_types,
                    "Hay valores de titularidad/suplencia no reconocidos.",
                )
            )

    return issues


def _negative_values(table_name: str, dataframe: pd.DataFrame, columns: list[str]) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for column in columns:
        if column in dataframe.columns:
            numeric = pd.to_numeric(dataframe[column], errors="coerce")
            count = int((numeric < 0).sum())
            if count > 0:
                issues.append(
                    QualityIssue(
                        table_name,
                        "error",
                        "negative_values",
                        column,
                        count,
                        f"La columna '{column}' tiene {count} valores negativos.",
                    )
                )
    return issues


def _issues_to_frame(issues: list[QualityIssue]) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame(columns=["table", "severity", "issue", "column", "count", "message"])
    return pd.DataFrame([issue.__dict__ for issue in issues])

