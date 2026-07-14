# ProcureIQ Architecture

## Layers

1. **Ingestion / seed** (`etl/`) — synthetic ERP stand-ins → PostgreSQL star schema + DQ gates  
2. **Semantic product layer** (`semantic/views.sql`) — governed cubes & metrics  
3. **Data products API** (`api/`) — FastAPI with API-key auth & structured logs  
4. **Decision UI** (`dashboard/`) — Streamlit executive analytics product  
5. **AI agent** (`agent/`) — LangGraph (or deterministic router) over **semantic views only**

## Design principles

1. Single source of truth for spend at invoice/PO grain (`fact_spend`).  
2. Semantic views are the contract — BI and LLM share definitions.  
3. Agents never bypass the semantic layer to hit raw dims/facts.  
4. DQ gates in ETL surface nulls, duplicate PO lines, negative amounts.  
5. Cloud-portable: Postgres locally ↔ Fabric Warehouse / Aurora / RDS in enterprise.

## Star schema

```
dim_supplier ─┐
dim_category ─┼─ fact_spend
dim_contract ─┘
```

## Semantic views

| View | Decision job |
|---|---|
| `v_spend_cube` | Supplier × category × period aggregation |
| `v_price_variance` | Negotiated vs actual; flag >5% |
| `v_tco_by_supplier` | Invoice + risk/quality + switching |
| `v_pvm_monthly` | Price / volume / mix MoM |
| `v_maverick_spend` | Off-contract activity |
| `v_executive_monthly` | CPO / Finance pulse |

## Security / portfolio notes

Synthetic data only. Production: RLS by BU, secret-managed API keys, PII vault separate from spend facts, audit agent prompts + SQL.
