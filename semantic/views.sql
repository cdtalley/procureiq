-- ProcureIQ semantic layer
-- Contract for BI tools AND the LangGraph agent — agents query these views only.

create schema if not exists semantic;

create or replace view semantic.v_spend_cube as
select
    date_trunc('month', f.spend_date)::date as period_month,
    s.supplier_id,
    s.name as supplier_name,
    s.risk_tier,
    s.region,
    c.category_id,
    c.name as category_name,
    c.parent_category,
    c.direct_or_indirect,
    f.cost_center,
    count(*) as txn_count,
    sum(f.quantity) as volume,
    round(sum(f.invoice_amount)::numeric, 2) as spend,
    round(avg(f.actual_rate)::numeric, 4) as avg_actual_rate,
    round(avg(f.negotiated_rate)::numeric, 4) as avg_negotiated_rate
from fact_spend f
join dim_supplier s on s.supplier_id = f.supplier_id
join dim_category c on c.category_id = f.category_id
where f.invoice_amount >= 0
group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10;

create or replace view semantic.v_price_variance as
select
    f.transaction_id,
    f.spend_date,
    date_trunc('month', f.spend_date)::date as period_month,
    s.supplier_id,
    s.name as supplier_name,
    c.name as category_name,
    c.direct_or_indirect,
    f.po_number,
    f.contract_id,
    f.quantity,
    f.negotiated_rate,
    f.actual_rate,
    round((f.actual_rate - f.negotiated_rate)::numeric, 4) as rate_variance,
    round(
        case
            when f.negotiated_rate is null or f.negotiated_rate = 0 then null
            else ((f.actual_rate - f.negotiated_rate) / f.negotiated_rate * 100)
        end::numeric,
        2
    ) as variance_pct,
    round(((f.actual_rate - coalesce(f.negotiated_rate, f.actual_rate)) * f.quantity)::numeric, 2)
        as leakage_amount,
    case
        when f.negotiated_rate is not null
             and f.negotiated_rate > 0
             and ((f.actual_rate - f.negotiated_rate) / f.negotiated_rate) > 0.05
        then true
        else false
    end as variance_flag
from fact_spend f
join dim_supplier s on s.supplier_id = f.supplier_id
join dim_category c on c.category_id = f.category_id
where f.invoice_amount >= 0
  and f.contract_id is not null
  and f.negotiated_rate is not null;

create or replace view semantic.v_tco_by_supplier as
select
    s.supplier_id,
    s.name as supplier_name,
    s.risk_tier,
    s.region,
    round(sum(f.invoice_amount)::numeric, 2) as invoice_spend,
    round(
        sum(f.invoice_amount) * case s.risk_tier
            when 'High' then 0.08
            when 'Medium' then 0.04
            else 0.015
        end
    ::numeric, 2) as risk_quality_cost,
    round(
        sum(f.invoice_amount) * case s.risk_tier
            when 'High' then 0.05
            when 'Medium' then 0.02
            else 0.01
        end
    ::numeric, 2) as switching_cost_est,
    round(
        (
            sum(f.invoice_amount)
            + sum(f.invoice_amount) * case s.risk_tier
                when 'High' then 0.08 when 'Medium' then 0.04 else 0.015 end
            + sum(f.invoice_amount) * case s.risk_tier
                when 'High' then 0.05 when 'Medium' then 0.02 else 0.01 end
        )::numeric,
        2
    ) as tco
from fact_spend f
join dim_supplier s on s.supplier_id = f.supplier_id
where f.invoice_amount >= 0
group by 1, 2, 3, 4;

create or replace view semantic.v_maverick_spend as
select
    f.transaction_id,
    f.spend_date,
    date_trunc('month', f.spend_date)::date as period_month,
    s.supplier_id,
    s.name as supplier_name,
    c.name as category_name,
    c.direct_or_indirect,
    f.po_number,
    f.cost_center,
    round(f.invoice_amount::numeric, 2) as spend,
    f.is_maverick
from fact_spend f
join dim_supplier s on s.supplier_id = f.supplier_id
join dim_category c on c.category_id = f.category_id
where f.is_maverick = true
  and f.invoice_amount >= 0;

create or replace view semantic.v_executive_monthly as
select
    date_trunc('month', f.spend_date)::date as period_month,
    round(sum(f.invoice_amount)::numeric, 2) as total_spend,
    round(sum(case when c.direct_or_indirect = 'Direct' then f.invoice_amount else 0 end)::numeric, 2)
        as direct_spend,
    round(sum(case when c.direct_or_indirect = 'Indirect' then f.invoice_amount else 0 end)::numeric, 2)
        as indirect_spend,
    round(sum(case when f.is_maverick then f.invoice_amount else 0 end)::numeric, 2) as maverick_spend,
    round(
        sum(
            case
                when f.contract_id is not null
                     and f.negotiated_rate is not null
                     and f.actual_rate > f.negotiated_rate * 1.05
                then (f.actual_rate - f.negotiated_rate) * f.quantity
                else 0
            end
        )::numeric,
        2
    ) as rate_leakage,
    count(*) as txn_count
from fact_spend f
join dim_category c on c.category_id = f.category_id
where f.invoice_amount >= 0
group by 1;

-- Price / volume / mix vs prior month at category grain
create or replace view semantic.v_pvm_monthly as
with monthly as (
    select
        date_trunc('month', f.spend_date)::date as period_month,
        c.category_id,
        c.name as category_name,
        c.direct_or_indirect,
        sum(f.quantity) as volume,
        sum(f.invoice_amount) as spend,
        sum(f.invoice_amount) / nullif(sum(f.quantity), 0) as avg_price
    from fact_spend f
    join dim_category c on c.category_id = f.category_id
    where f.invoice_amount >= 0
    group by 1, 2, 3, 4
),
lagged as (
    select
        m.*,
        lag(m.volume) over (partition by m.category_id order by m.period_month) as prev_volume,
        lag(m.spend) over (partition by m.category_id order by m.period_month) as prev_spend,
        lag(m.avg_price) over (partition by m.category_id order by m.period_month) as prev_price
    from monthly m
)
select
    period_month,
    category_id,
    category_name,
    direct_or_indirect,
    round(spend::numeric, 2) as spend,
    round((spend - prev_spend)::numeric, 2) as spend_change,
    round(((avg_price - prev_price) * volume)::numeric, 2) as price_effect,
    round((prev_price * (volume - prev_volume))::numeric, 2) as volume_effect,
    round(
        (
            (spend - prev_spend)
            - ((avg_price - prev_price) * volume)
            - (prev_price * (volume - prev_volume))
        )::numeric,
        2
    ) as mix_effect
from lagged
where prev_volume is not null;
