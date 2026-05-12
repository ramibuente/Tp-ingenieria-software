from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from sports_analytics.config import PARQUET_DIR, RAW_DIR
from sports_analytics.data_catalog import TABLES
from sports_analytics.etl.normalize import normalize_dataframe


DEFAULT_CHUNKSIZE = 250_000


def _normalize_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    return normalize_dataframe("unknown", chunk)


def convert_table_to_parquet(
    table_name: str,
    raw_dir: Path = RAW_DIR,
    parquet_dir: Path = PARQUET_DIR,
    chunksize: int = DEFAULT_CHUNKSIZE,
    overwrite: bool = True,
) -> Path:
    """Convierte un CSV grande en una carpeta Parquet particionada por chunks."""
    spec = TABLES[table_name]
    csv_path = raw_dir / spec.file_name
    output_dir = parquet_dir / table_name

    if not csv_path.exists():
        raise FileNotFoundError(f"No existe {csv_path}")

    if overwrite and output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    reader = pd.read_csv(csv_path, chunksize=chunksize, low_memory=False)
    for part_number, chunk in enumerate(tqdm(reader, desc=table_name)):
        normalized = normalize_dataframe(table_name, chunk, source_file=spec.file_name)
        normalized["_source_chunk"] = part_number
        part_path = output_dir / f"part-{part_number:05d}.parquet"
        normalized.to_parquet(part_path, index=False)

    return output_dir


def convert_all_to_parquet(
    raw_dir: Path = RAW_DIR,
    parquet_dir: Path = PARQUET_DIR,
    chunksize: int = DEFAULT_CHUNKSIZE,
    overwrite: bool = True,
) -> list[Path]:
    outputs = []
    for table_name in TABLES:
        outputs.append(
            convert_table_to_parquet(
                table_name,
                raw_dir=raw_dir,
                parquet_dir=parquet_dir,
                chunksize=chunksize,
                overwrite=overwrite,
            )
        )
    return outputs
