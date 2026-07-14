"""Silver layer - cleansed, conformed master data + standardized txs."""

from __future__ import annotations

from pathlib import Path

import duckdb

from src.paths import WAREHOUSE_DB, ensure_dirs


def run(db_path: Path | None = None) -> Path:
    ensure_dirs()
    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db))
    con.execute("create schema if not exists silver")

    # Supplier MDM: fuzzy-ish duplicate flag via normalized name
    con.execute(
        """
        create or replace table silver.suppliers as
        with base as (
            select
                supplier_id,
                trim(supplier_name) as supplier_name,
                supplier_name_alias,
                upper(regexp_replace(coalesce(supplier_name_alias, supplier_name), '[^A-Z0-9]', '', 'g')) as name_key,
                country,
                tier,
                primary_category_id,
                payment_terms_days,
                cast(diversity_flag as boolean) as diversity_flag,
                cast(active_flag as boolean) as active_flag,
                risk_score_seed,
                on_time_delivery_hist,
                quality_ppm_hist,
                _loaded_at_utc
            from bronze.bronze_suppliers
            where supplier_id is not null and supplier_name is not null
        ),
        dupes as (
            select name_key, count(*) as name_key_count
            from base
            group by 1
            having count(*) > 1
        )
        select
            b.*,
            coalesce(d.name_key_count > 1, false) as potential_duplicate_flag
        from base b
        left join dupes d using (name_key)
        """
    )

    con.execute(
        """
        create or replace table silver.categories as
        select
            category_id,
            category_code,
            category_l1,
            category_l2,
            category_l3,
            unspsc_stub,
            preferred_currency,
            category_l1 in ('Direct', 'Indirect') as hierarchy_valid
        from bronze.bronze_categories
        where category_id is not null
        """
    )

    con.execute(
        """
        create or replace table silver.contracts as
        select
            contract_id,
            supplier_id,
            category_id,
            contract_name,
            cast(start_date as date) as start_date,
            cast(end_date as date) as end_date,
            case
                when cast(end_date as date) < current_date then 'Expired'
                when cast(start_date as date) > current_date then 'Future'
                else coalesce(nullif(status, ''), 'Active')
            end as status,
            cast(unit_price as double) as unit_price,
            currency,
            volume_commitment,
            rebate_pct,
            escalation_pct
        from bronze.bronze_contracts
        where unit_price > 0
        """
    )

    con.execute(
        """
        create or replace table silver.should_cost as
        select
            category_id,
            material_cost,
            labor_cost,
            overhead_cost,
            freight_cost,
            quality_cost,
            should_cost_unit,
            model_version,
            confidence
        from bronze.bronze_should_cost
        """
    )

    con.execute(
        """
        create or replace table silver.cost_centers as
        select * from bronze.bronze_cost_centers
        """
    )

    con.execute(
        """
        create or replace table silver.purchase_orders as
        select
            po_id,
            po_line,
            cast(po_date as date) as po_date,
            supplier_id,
            category_id,
            contract_id,
            cost_center_id,
            business_unit,
            cast(qty as double) as qty,
            uom,
            cast(unit_price as double) as unit_price,
            cast(po_amount as double) as po_amount,
            currency,
            buyer_id,
            status
        from bronze.bronze_purchase_orders
        where qty > 0 and unit_price >= 0
        """
    )

    con.execute(
        """
        create or replace table silver.invoices as
        select
            invoice_id,
            invoice_line,
            cast(invoice_date as date) as invoice_date,
            po_id,
            supplier_id,
            category_id,
            contract_id,
            cost_center_id,
            business_unit,
            cast(qty as double) as qty,
            cast(unit_price as double) as actual_unit_price,
            cast(invoice_amount as double) as invoice_amount,
            currency,
            payment_status,
            cast(maverick_flag as boolean) as maverick_flag,
            cast(contracted_unit_price as double) as contracted_unit_price,
            cast(baseline_unit_price as double) as baseline_unit_price,
            cast(should_cost_unit as double) as should_cost_unit,
            cast(savings_realized as double) as savings_realized,
            cast(freight_cost as double) as freight_cost,
            cast(quality_cost as double) as quality_cost,
            cast(payment_terms_cost as double) as payment_terms_cost,
            cast(tco_amount as double) as tco_amount,
            cast(on_contract as boolean) as on_contract,
            date_trunc('month', cast(invoice_date as date)) as period_month
        from bronze.bronze_invoices
        where invoice_amount is not null
          and (po_id is not null or cast(maverick_flag as boolean) = true)
        """
    )

    con.execute(
        """
        create or replace table silver.gl_actuals as
        select
            gl_period,
            cost_center_id,
            category_id,
            gl_account,
            cast(actual_amount as double) as actual_amount,
            cast(budget_amount as double) as budget_amount,
            cast(forecast_amount as double) as forecast_amount
        from bronze.bronze_gl_actuals
        """
    )

    # Data quality results
    con.execute(
        """
        create or replace table silver.data_quality_results as
        select * from (
            select 'supplier_master_completeness' as rule_name,
                   (select count(*) from silver.suppliers) as rows_passed,
                   (select count(*) from bronze.bronze_suppliers) as rows_source,
                   current_timestamp as checked_at
            union all
            select 'invoice_po_or_maverick',
                   (select count(*) from silver.invoices),
                   (select count(*) from bronze.bronze_invoices),
                   current_timestamp
            union all
            select 'category_hierarchy_valid',
                   (select count(*) from silver.categories where hierarchy_valid),
                   (select count(*) from silver.categories),
                   current_timestamp
            union all
            select 'supplier_potential_duplicates',
                   (select count(*) from silver.suppliers where potential_duplicate_flag),
                   (select count(*) from silver.suppliers),
                   current_timestamp
        )
        """
    )

    con.close()
    print(f"Silver transform complete -> {db}")
    return db


if __name__ == "__main__":
    run()
