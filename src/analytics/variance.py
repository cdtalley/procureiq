"""
Price–Volume–Mix (PVM) variance decomposition.

Compares current period vs prior period (or baseline) to separate
rate, volume, and mix effects - core procurement finance narrative.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.paths import DATA_EXPORTS, WAREHOUSE_DB, ensure_dirs


def compute_pvm(db_path: Path | None = None) -> pd.DataFrame:
    """
    Category-level PVM vs prior month:
      price_effect  = (P1 - P0) * Q1
      volume_effect = P0 * (Q1 - Q0)   [category quantity change at prior mix-neutral price]
      mix approximated via residual vs total spend change after price+volume
    """
    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db), read_only=True)
    monthly = con.execute(
        """
        select
            period_month,
            category_id,
            max(category_l3) as category_l3,
            max(spend_type) as spend_type,
            sum(qty) as volume,
            sum(invoice_amount) as spend,
            sum(invoice_amount) / nullif(sum(qty), 0) as avg_price
        from gold.fact_spend
        group by 1, 2
        """
    ).df()
    con.close()

    monthly = monthly.sort_values(["category_id", "period_month"])
    monthly["prev_volume"] = monthly.groupby("category_id")["volume"].shift(1)
    monthly["prev_spend"] = monthly.groupby("category_id")["spend"].shift(1)
    monthly["prev_price"] = monthly.groupby("category_id")["avg_price"].shift(1)

    cur = monthly.dropna(subset=["prev_volume", "prev_price"]).copy()
    cur["price_effect"] = (cur["avg_price"] - cur["prev_price"]) * cur["volume"]
    cur["volume_effect"] = cur["prev_price"] * (cur["volume"] - cur["prev_volume"])
    cur["spend_change"] = cur["spend"] - cur["prev_spend"]
    cur["mix_effect"] = cur["spend_change"] - cur["price_effect"] - cur["volume_effect"]
    return cur


def summarize_pvm(pvm: pd.DataFrame) -> pd.DataFrame:
    latest = pvm["period_month"].max()
    snap = pvm[pvm["period_month"] == latest].copy()
    return (
        snap.groupby(["spend_type", "category_l3"], as_index=False)[
            ["spend", "spend_change", "price_effect", "volume_effect", "mix_effect"]
        ]
        .sum()
        .sort_values("spend_change", ascending=False)
    )


def run(db_path: Path | None = None) -> Path:
    ensure_dirs()
    DATA_EXPORTS.mkdir(parents=True, exist_ok=True)
    pvm = compute_pvm(db_path)
    summary = summarize_pvm(pvm)
    out_detail = DATA_EXPORTS / "pvm_detail.parquet"
    out_summary = DATA_EXPORTS / "pvm_summary.csv"
    pvm.to_parquet(out_detail, index=False)
    summary.to_csv(out_summary, index=False)

    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db))
    con.execute("create schema if not exists analytics")
    con.execute("create or replace table analytics.pvm_category_monthly as select * from pvm")
    con.execute("create or replace table analytics.pvm_latest_summary as select * from summary")
    con.close()
    print(f"PVM analytics written -> {out_summary}")
    return out_summary


if __name__ == "__main__":
    run()
