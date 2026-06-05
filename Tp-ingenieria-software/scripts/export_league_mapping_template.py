from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

from sports_analytics.config import INTERIM_DIR, RAW_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera una plantilla para mapear competencias locales a league_id de API-Football.")
    parser.add_argument("--output", type=Path, default=INTERIM_DIR / "api_football_league_mapping_template.csv")
    args = parser.parse_args()

    competitions_path = RAW_DIR / "competitions.csv"
    if not competitions_path.exists():
        print(f"No existe {competitions_path}. Primero descarguen los CSV historicos.")
        return 1

    competitions = pd.read_csv(competitions_path)
    columns = [column for column in ["competition_id", "name", "country_name", "type", "sub_type"] if column in competitions.columns]
    mapping = competitions[columns].drop_duplicates().sort_values(columns[:1]).copy()
    mapping["api_football_league_id"] = ""
    mapping["enabled"] = False
    mapping["notes"] = ""

    args.output.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(args.output, index=False)
    print(f"Plantilla generada en {args.output}")
    print("Completar api_football_league_id con los IDs encontrados en API-Football > Documentation > Leagues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
