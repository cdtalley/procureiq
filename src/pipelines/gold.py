"""Gold layer - dimensional model + analytical spend cube."""

from __future__ import annotations

from pathlib import Path

import duckdb

from src.paths import WAREHOUSE_DB, ensure_dirs


def run(db_path: Path | None = None) -> Path:
    ensure_dirs()
    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db))
    con.execute("create schema if not exists gold")

    con.execute(
        """
        create or replace table gold.dim_supplier as
        select
            supplier_id,
            supplier_name,
            country as supplier_country,
            tier as supplier_tier,
            primary_category_id,
            payment_terms_days,
            diversity_flag,
            active_flag,
            potential_duplicate_flag,
            risk_score_seed,
            on_time_delivery_hist,
            quality_ppm_hist
        from silver.suppliers
        """
    )

    con.execute(
        """
        create or replace table gold.dim_category as
        select
            category_id,
            category_code,
            category_l1 as spend_type,
            category_l1,
            category_l2,
            category_l3,
            unspsc_stub
        from silver.categories
        """
    )

    con.execute(
        """
        create or replace table gold.dim_contract as
        select
            contract_id,
            supplier_id,
            category_id,
            contract_name,
            start_date,
            end_date,
            status as contract_status,
            unit_price as contracted_rate,
            volume_commitment,
            rebate_pct,
            escalation_pct
        from silver.contracts
        """
    )

    con.execute(
        """
        create or replace table gold.dim_cost_center as
        select * from silver.cost_centers
        """
    )

    con.execute(
        """
        create or replace table gold.dim_calendar as
        with bounds as (
            select min(invoice_date) as dmin, max(invoice_date) as dmax
            from silver.invoices
        ),
        series as (
            select unnest(generate_series(dmin, dmax, interval '1 day'))::date as calendar_date
            from bounds
        )
        select
            strftime(calendar_date, '%Y%m%d')::int as date_key,
            calendar_date,
            date_trunc('month', calendar_date)::date as month_start,
            extract(year from calendar_date)::int as fiscal_year,
            extract(quarter from calendar_date)::int as fiscal_quarter,
            extract(month from calendar_date)::int as fiscal_month,
            strftime(calendar_date, '%Y-%m') as year_month
        from series
        """
    )

    # Atomic spend fact at invoice grain
    con.execute(
        """
        create or replace table gold.fact_spend as
        select
            i.invoice_id,
            i.invoice_line,
            i.invoice_date,
            strftime(i.invoice_date, '%Y%m%d')::int as date_key,
            i.period_month,
            i.po_id,
            i.supplier_id,
            i.category_id,
            i.contract_id,
            i.cost_center_id,
            i.business_unit,
            i.qty,
            i.actual_unit_price,
            i.contracted_unit_price,
            i.baseline_unit_price,
            i.should_cost_unit,
            i.invoice_amount,
            coalesce(p.po_amount, 0) as po_amount,
            i.contracted_unit_price * i.qty as contracted_amount,
            i.should_cost_unit * i.qty as should_cost_amount,
            (i.actual_unit_price - i.contracted_unit_price) * i.qty as price_variance,
            (i.actual_unit_price - i.should_cost_unit) * i.qty as should_cost_gap,
            i.savings_realized,
            i.freight_cost,
            i.quality_cost,
            i.payment_terms_cost,
            i.tco_amount,
            i.on_contract,
            i.maverick_flag,
            i.payment_status,
            c.category_l1 as spend_type,
            c.category_l2,
            c.category_l3
        from silver.invoices i
        left join silver.purchase_orders p on i.po_id = p.po_id and i.invoice_line = p.po_line
        left join silver.categories c on i.category_id = c.category_id
        """
    )

    # Analytical spend cube - multi-hierarchy aggregates (supplier × category × period)
    con.execute(
        """
        create or replace table gold.spend_cube as
        select
            period_month,
            spend_type,
            category_l2,
            category_l3,
            category_id,
            supplier_id,
            business_unit,
            cost_center_id,
            on_contract,
            maverick_flag,
            sum(qty) as volume,
            sum(invoice_amount) as spend,
            sum(po_amount) as po_spend,
            sum(contracted_amount) as contracted_spend,
            sum(should_cost_amount) as should_cost_spend,
            sum(price_variance) as rate_leakage,
            sum(should_cost_gap) as should_cost_gap,
            sum(savings_realized) as savings_realized,
            sum(tco_amount) as tco_spend,
            count(*) as invoice_lines,
            avg(actual_unit_price) as avg_unit_price,
            avg(contracted_unit_price) as avg_contract_price
        from gold.fact_spend
        group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
        """
    )

    # Executive monthly rollup
    con.execute(
        """
        create or replace table gold.mart_monthly_executive as
        select
            period_month,
            sum(invoice_amount) as total_spend,
            sum(case when spend_type = 'Direct' then invoice_amount else 0 end) as direct_spend,
            sum(case when spend_type = 'Indirect' then invoice_amount else 0 end) as indirect_spend,
            sum(case when on_contract then invoice_amount else 0 end) as on_contract_spend,
            sum(case when not on_contract then invoice_amount else 0 end) as off_contract_spend,
            sum(case when maverick_flag then invoice_amount else 0 end) as maverick_spend,
            sum(price_variance) as rate_leakage,
            sum(should_cost_gap) as should_cost_gap,
            sum(savings_realized) as savings_realized,
            sum(tco_amount) as tco_spend,
            count(distinct supplier_id) as active_suppliers,
            count(distinct category_id) as active_categories
        from gold.fact_spend
        group by 1
        order by 1
        """
    )

    con.execute(
        """
        create or replace table gold.mart_supplier_performance as
        select
            s.supplier_id,
            s.supplier_name,
            s.supplier_tier,
            s.supplier_country,
            s.diversity_flag,
            sum(f.invoice_amount) as total_spend,
            sum(f.price_variance) as rate_leakage,
            sum(f.should_cost_gap) as should_cost_gap,
            sum(case when f.on_contract then f.invoice_amount else 0 end)
                / nullif(sum(f.invoice_amount), 0) as contract_compliance_rate,
            sum(case when f.maverick_flag then f.invoice_amount else 0 end) as maverick_spend,
            avg(s.on_time_delivery_hist) as otd_rate,
            avg(s.quality_ppm_hist) as quality_ppm,
            count(*) as invoice_lines
        from gold.fact_spend f
        join gold.dim_supplier s on f.supplier_id = s.supplier_id
        group by 1, 2, 3, 4, 5
        """
    )

    con.execute(
        """
        create or replace table gold.mart_category_spend as
        select
            spend_type,
            category_l2,
            category_l3,
            category_id,
            sum(invoice_amount) as total_spend,
            sum(price_variance) as rate_leakage,
            sum(should_cost_gap) as should_cost_gap,
            sum(savings_realized) as savings_realized,
            sum(case when on_contract then invoice_amount else 0 end)
                / nullif(sum(invoice_amount), 0) as contract_compliance_rate,
            count(distinct supplier_id) as supplier_count
        from gold.fact_spend
        group by 1, 2, 3, 4
        """
    )

    con.execute(
        """
        create or replace table gold.mart_finance_alignment as
        select
            g.gl_period,
            g.cost_center_id,
            cc.cost_center_name,
            cc.business_unit,
            g.category_id,
            c.category_l1,
            c.category_l3,
            g.gl_account,
            sum(g.actual_amount) as actual_amount,
            sum(g.budget_amount) as budget_amount,
            sum(g.forecast_amount) as forecast_amount,
            sum(g.actual_amount) - sum(g.budget_amount) as budget_variance
        from silver.gl_actuals g
        left join gold.dim_cost_center cc on g.cost_center_id = cc.cost_center_id
        left join gold.dim_category c on g.category_id = c.category_id
        group by 1, 2, 3, 4, 5, 6, 7, 8
        """
    )

    con.close()
    print(f"Gold dimensional model + spend cube complete -> {db}")
    return db


if __name__ == "__main__":
    run()
