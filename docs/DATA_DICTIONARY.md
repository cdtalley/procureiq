# Data Dictionary (consumer-facing)

## Core entities

| Field | Definition |
|---|---|
| `supplier_id` | Surrogate key from MDM |
| `category_l1` / `spend_type` | Direct or Indirect |
| `category_l2` / `category_l3` | Category hierarchy |
| `contract_id` | Negotiated agreement key |
| `on_contract` | Invoice linked to active contract rate path |
| `maverick_flag` | Invoice without PO (non-PO / after-the-fact) |

## Measures

| Measure | Definition |
|---|---|
| `invoice_amount` | Amount invoiced/paid (actual spend) |
| `po_amount` | Committed PO value |
| `contracted_amount` | `qty × contracted_unit_price` |
| `should_cost_amount` | `qty × should_cost_unit` |
| `price_variance` / rate leakage | `(actual - contracted) × qty` |
| `should_cost_gap` | `(actual - should_cost) × qty` |
| `savings_realized` | vs baseline price (Finance-aligned demo) |
| `tco_amount` | Invoice + freight + quality + payment-terms cost |

## Risk

| Field | Definition |
|---|---|
| `supplier_risk_score` | 0–1 composite: operational, commercial, concentration |
| `risk_tier` | Low / Medium / High |
| `is_anomaly` | Isolation Forest flag on invoice features |