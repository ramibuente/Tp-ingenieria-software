from __future__ import annotations

import argparse
import sys

from sports_analytics.data_catalog import TABLES
from sports_analytics.etl.csv_to_parquet import DEFAULT_CHUNKSIZE, convert_all_to_parquet, convert_table_to_parquet
from sports_analytics.etl.validate_raw import validate_all, validate_table


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida CSV y los convierte a Parquet por chunks.")
    parser.add_argument("--table", choices=TABLES.keys(), help="Nombre de una tabla puntual. Si se omite, procesa todas.")
    parser.add_argument("--chunksize", type=int, default=DEFAULT_CHUNKSIZE)
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()

    if not args.skip_validation:
        results = [validate_table(args.table)] if args.table else validate_all()
        failed = [result for result in results if not result.ok]
        for result in results:
            status = "OK" if result.ok else "ERROR"
            print(f"{status} {result.table}: {result.message}")
        if failed:
            return 1

    try:
        if args.table:
            output = convert_table_to_parquet(args.table, chunksize=args.chunksize)
            print(f"Parquet generado en {output}")
        else:
            outputs = convert_all_to_parquet(chunksize=args.chunksize)
            print("Parquet generado:")
            for output in outputs:
                print(f"- {output}")
    except ImportError as exc:
        print("Falta una dependencia para Parquet. Ejecutar: pip install -r requirements.txt")
        print(exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
