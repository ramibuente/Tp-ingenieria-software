from __future__ import annotations

import pandas as pd

from sports_analytics.config import RAW_DIR
from sports_analytics.data_catalog import TABLES


def main() -> int:
    rows = []
    for table_name, spec in TABLES.items():
        csv_path = RAW_DIR / spec.file_name
        if not csv_path.exists():
            rows.append({"table": table_name, "status": "missing", "rows_sampled": 0, "columns": 0})
            continue

        sample = pd.read_csv(csv_path, nrows=10_000, low_memory=False)
        rows.append(
            {
                "table": table_name,
                "status": "ok",
                "rows_sampled": len(sample),
                "columns": len(sample.columns),
                "null_cells_sample": int(sample.isna().sum().sum()),
            }
        )

    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

