-- Gold dimensional reference (portable to Fabric / Snowflake / BigQuery)
-- fact_spend grain: invoice line

-- dim_supplier
-- dim_category (L1 Direct/Indirect → L2 → L3)
-- dim_contract
-- dim_cost_center
-- dim_calendar
-- fact_spend
-- spend_cube (supplier × category × period aggregates)

create or replace view gold.v_spend_under_management as
select
    spend_type,
    round(sum(invoice_amount), 2) as spend,
    round(sum(case when on_contract then invoice_amount else 0 end), 2) as on_contract_spend,
    round(
        100.0 * sum(case when on_contract then invoice_amount else 0 end)
        / nullif(sum(invoice_amount), 0),
        2
    ) as compliance_pct
from gold.fact_spend
group by 1;

create or replace view gold.v_top_leakage_suppliers as
select
    s.supplier_name,
    s.supplier_tier,
    round(sum(f.price_variance), 2) as rate_leakage,
    round(sum(f.invoice_amount), 2) as spend
from gold.fact_spend f
join gold.dim_supplier s on f.supplier_id = s.supplier_id
group by 1, 2
having sum(f.price_variance) > 0
order by rate_leakage desc
limit 50;
