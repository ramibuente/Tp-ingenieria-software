from __future__ import annotations

from pathlib import Path

import pandas as pd

from sports_analytics.config import PARQUET_DIR, RAW_DIR
from sports_analytics.data_catalog import TABLES
from sports_analytics.etl.normalize import normalize_dataframe


def data_version(table_name: str) -> tuple[float, ...]:
    """Version liviana para invalidar caches cuando cambian CSV o Parquet."""
    spec = TABLES[table_name]
    paths = []
    csv_path = RAW_DIR / spec.file_name
    parquet_path = PARQUET_DIR / table_name

    if csv_path.exists():
        paths.append(csv_path)
    if parquet_path.exists():
        paths.extend(sorted(parquet_path.glob("*.parquet")))

    return tuple(path.stat().st_mtime for path in paths)


def load_table(table_name: str, prefer_parquet: bool = True) -> pd.DataFrame:
    spec = TABLES[table_name]
    parquet_path = PARQUET_DIR / table_name

    if prefer_parquet and parquet_path.exists():
        return normalize_dataframe(table_name, pd.read_parquet(parquet_path))

    return normalize_dataframe(table_name, pd.read_csv(RAW_DIR / spec.file_name, low_memory=False))


def load_table_columns(table_name: str, columns: list[str], prefer_parquet: bool = True) -> pd.DataFrame:
    spec = TABLES[table_name]
    parquet_path = PARQUET_DIR / table_name

    if prefer_parquet and parquet_path.exists():
        try:
            return normalize_dataframe(table_name, pd.read_parquet(parquet_path, columns=columns))
        except Exception as exc:
            if not (RAW_DIR / spec.file_name).exists():
                raise
            print(f"No se pudo leer Parquet de {table_name}; se usa CSV original. Detalle: {exc}")

    return normalize_dataframe(table_name, pd.read_csv(RAW_DIR / spec.file_name, usecols=columns, low_memory=False))


def load_table_filtered_by_value(
    table_name: str,
    columns: list[str],
    filter_column: str,
    value: object,
    chunksize: int = 250_000,
) -> pd.DataFrame:
    spec = TABLES[table_name]
    parquet_path = PARQUET_DIR / table_name

    if parquet_path.exists():
        try:
            data = pd.read_parquet(parquet_path, columns=columns)
        except Exception as exc:
            if not (RAW_DIR / spec.file_name).exists():
                raise
            print(f"No se pudo leer Parquet de {table_name}; se usa CSV original. Detalle: {exc}")
        else:
            return normalize_dataframe(table_name, data[data[filter_column] == value])

    parts = []
    for chunk in pd.read_csv(RAW_DIR / spec.file_name, usecols=columns, chunksize=chunksize, low_memory=False):
        parts.append(chunk[chunk[filter_column] == value])

    if not parts:
        return pd.DataFrame(columns=columns)
    return normalize_dataframe(table_name, pd.concat(parts, ignore_index=True))


def table_exists(table_name: str, base_dir: Path = PARQUET_DIR) -> bool:
    return (base_dir / table_name).exists() or (RAW_DIR / TABLES[table_name].file_name).exists()
