# ProcureIQ Architecture

## Design principles

1. **Single source of truth for spend** — invoices as the financial grain; POs/contracts/should-cost join in.
2. **Medallion boundaries** — bronze immutable land; silver conformed; gold consumer-ready.
3. **Productized marts** — every gold/analytics table answers a named use case.
4. **Semantic governance** — metrics defined once in YAML; BI and LLM share definitions.
5. **Cloud-portable SQL** — DuckDB locally; same star schema lands in Fabric Warehouse / Snowflake.

## Source integration (simulated enterprise)

| Source | System stand-in | Entities |
|---|---|---|
| Purchase orders | SAP S/4 | Commitments, buyers, qty/price |
| Invoices | Oracle AP | Actual spend, payment status |
| Contracts | Coupa CLM | Negotiated rates, term windows |
| Supplier master | MDM | Tier, locality, risk seeds, aliases |
| Category taxonomy | Category Mgmt | Direct/Indirect L1–L3 |
| GL actuals | Oracle GL | Budget, forecast, actual by CC |
| Should-cost | Eng + Finance | Component cost build-up |

## Dimensional model

```
dim_supplier ─┐
dim_category ─┼─ fact_spend ─ spend_cube
dim_contract ─┤       │
dim_cost_center┤      ├── mart_monthly_executive
dim_calendar ─┘       ├── mart_supplier_performance
                      ├── mart_category_spend
                      └── mart_finance_alignment
```

**Fact grain:** one row per invoice line.

**Key measures:** `invoice_amount`, `qty`, `price_variance`, `should_cost_gap`, `savings_realized`, `tco_amount`, `on_contract`, `maverick_flag`.

## Data quality gates (silver)

| Rule | Intent |
|---|---|
| Supplier completeness | Block null master keys |
| Invoice PO or maverick | Referential integrity with intentional exception path |
| Category hierarchy valid | Direct/Indirect taxonomy integrity |
| Potential duplicate flag | MDM stewardship queue |

## Orchestration contract (for offshore / platform teams)

`configs/pipeline.yaml` defines:

- Source file contracts
- Layer order: bronze → silver → gold → analytics → ml
- Quality rules ownership

Hands-on design ownership stays with the analytics product owner; execution can be dotted-line.

## AI-ready foundation

`configs/semantic_layer.yaml` declares:

- Entities & primary keys
- Measures and derived metrics (compliance, maverick %, leakage)
- LLM use cases: NL spend query, negotiation prep, leakage RCAs

`src/ml/semantic_qa.py` resolves NL → intent → governed SQL. Swap the intent router for an LLM tool-caller without changing marts.

## Security / privacy notes (portfolio)

Synthetic data only. In production: row-level security by BU, tokenize supplier bank details, separate PII vault from spend facts, audit semantic QA prompts.