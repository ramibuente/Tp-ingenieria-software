from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from sports_analytics.config import RAW_DIR
from sports_analytics.data_catalog import TABLES
from sports_analytics.etl.quality import build_quality_report, build_quality_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera reportes de calidad sobre los CSV originales.")
    parser.add_argument("--table", choices=TABLES.keys(), help="Tabla a revisar. Si se omite, revisa todas.")
    parser.add_argument("--sample-rows", type=int, default=50_000)
    parser.add_argument("--output", type=Path, help="CSV donde guardar el detalle del reporte.")
    args = parser.parse_args()

    table_names = [args.table] if args.table else list(TABLES.keys())
    reports = []
    summaries = []

    for table_name in table_names:
        spec = TABLES[table_name]
        csv_path = RAW_DIR / spec.file_name
        if not csv_path.exists():
            reports.append(
                pd.DataFrame(
                    [
                        {
                            "table": table_name,
                            "severity": "error",
                            "issue": "missing_file",
                            "column": "*",
                            "count": 1,
                            "message": f"No existe {csv_path}",
                        }
                    ]
                )
            )
            continue

        sample = pd.read_csv(csv_path, nrows=args.sample_rows, low_memory=False)
        reports.append(build_quality_report(table_name, sample))
        summaries.append(build_quality_summary(table_name, sample))

    report = pd.concat(reports, ignore_index=True) if reports else pd.DataFrame()
    summary = pd.DataFrame(summaries)

    print("Resumen")
    print(summary.to_string(index=False) if not summary.empty else "Sin tablas procesadas.")
    print("\nDetalle")
    print(report.to_string(index=False) if not report.empty else "Sin problemas detectados.")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.output, index=False)
        print(f"\nReporte guardado en {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

