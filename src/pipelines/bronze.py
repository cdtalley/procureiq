"""Bronze layer - land raw multi-system extracts with load metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from src.paths import DATA_RAW, WAREHOUSE_DB, ensure_dirs

BRONZE_TABLES = {
    "bronze_suppliers": "suppliers.csv",
    "bronze_categories": "categories.csv",
    "bronze_contracts": "contracts.csv",
    "bronze_should_cost": "should_cost.csv",
    "bronze_purchase_orders": "purchase_orders.csv",
    "bronze_invoices": "invoices.csv",
    "bronze_gl_actuals": "gl_actuals.csv",
    "bronze_cost_centers": "cost_centers.csv",
}


def run(raw_dir: Path | None = None, db_path: Path | None = None) -> Path:
    ensure_dirs()
    raw = Path(raw_dir) if raw_dir else DATA_RAW
    db = Path(db_path) if db_path else WAREHOUSE_DB
    db.parent.mkdir(parents=True, exist_ok=True)

    load_ts = datetime.now(timezone.utc).isoformat()
    con = duckdb.connect(str(db))
    con.execute("create schema if not exists bronze")

    for table, fname in BRONZE_TABLES.items():
        path = raw / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing source extract: {path}. Run generate_data.py first.")
        df = pd.read_csv(path)
        df["_source_file"] = fname
        df["_loaded_at_utc"] = load_ts
        con.execute(f"create or replace table bronze.{table} as select * from df")

    con.execute(
        """
        create or replace table bronze._load_manifest as
        select
            ? as loaded_at_utc,
            ? as source_system_count,
            ? as row_count_total
        """,
        [load_ts, len(BRONZE_TABLES), sum(len(pd.read_csv(raw / f)) for f in BRONZE_TABLES.values())],
    )
    con.close()
    print(f"Bronze load complete -> {db}")
    return db


if __name__ == "__main__":
    run()
