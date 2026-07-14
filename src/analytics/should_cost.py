"""Should-cost gap, rate leakage, and TCO analytics products."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.paths import DATA_EXPORTS, WAREHOUSE_DB, ensure_dirs


def build_leakage_mart(db_path: Path | None = None) -> dict[str, pd.DataFrame]:
    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db), read_only=True)

    leakage = con.execute(
        """
        select
            s.supplier_id,
            s.supplier_name,
            s.supplier_tier,
            f.spend_type,
            f.category_l3,
            sum(f.invoice_amount) as spend,
            sum(f.price_variance) as rate_leakage,
            sum(f.should_cost_gap) as should_cost_gap,
            sum(f.maverick_flag::int * f.invoice_amount) as maverick_spend,
            sum(case when f.on_contract then 0 else f.invoice_amount end) as off_contract_spend,
            sum(f.price_variance) / nullif(sum(f.invoice_amount), 0) as leakage_rate_pct,
            sum(f.should_cost_gap) / nullif(sum(f.invoice_amount), 0) as should_cost_gap_pct
        from gold.fact_spend f
        join gold.dim_supplier s on f.supplier_id = s.supplier_id
        group by 1, 2, 3, 4, 5
        having sum(f.invoice_amount) > 0
        order by rate_leakage desc
        """
    ).df()

    tco = con.execute(
        """
        select
            spend_type,
            category_l3,
            sum(invoice_amount) as invoice_spend,
            sum(freight_cost) as freight,
            sum(quality_cost) as quality,
            sum(payment_terms_cost) as payment_terms,
            sum(tco_amount) as tco,
            sum(tco_amount) - sum(invoice_amount) as tco_uplift,
            (sum(tco_amount) - sum(invoice_amount)) / nullif(sum(invoice_amount), 0) as tco_uplift_pct
        from gold.fact_spend
        group by 1, 2
        order by tco desc
        """
    ).df()

    opportunity = con.execute(
        """
        select
            'rate_leakage' as opportunity_type,
            sum(case when price_variance > 0 then price_variance else 0 end) as opportunity_usd,
            'Bridge paid unit price to contracted rate' as playbook
        from gold.fact_spend
        union all
        select
            'should_cost_gap',
            sum(case when should_cost_gap > 0 then should_cost_gap else 0 end),
            'Renegotiate or redesign where actual > should-cost'
        from gold.fact_spend
        union all
        select
            'maverick_spend',
            sum(case when maverick_flag then invoice_amount else 0 end),
            'Route off-PO spend to preferred suppliers / catalogs'
        from gold.fact_spend
        union all
        select
            'off_contract_spend',
            sum(case when not on_contract then invoice_amount else 0 end),
            'Increase contract coverage and enablement'
        from gold.fact_spend
        """
    ).df()

    con.close()
    return {"leakage": leakage, "tco": tco, "opportunity": opportunity}


def run(db_path: Path | None = None) -> Path:
    ensure_dirs()
    DATA_EXPORTS.mkdir(parents=True, exist_ok=True)
    marts = build_leakage_mart(db_path)

    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db))
    con.execute("create schema if not exists analytics")
    for name, frame in marts.items():
        con.execute(f"create or replace table analytics.{name} as select * from frame")
        frame.to_csv(DATA_EXPORTS / f"{name}.csv", index=False)
    con.close()
    print("Should-cost / leakage / TCO marts written")
    return DATA_EXPORTS / "opportunity.csv"


if __name__ == "__main__":
    run()
