# Product Roadmap — ProcureIQ

Acting as analytics product owner for Procurement.

## North-star outcomes

1. Increase **on-contract spend** by making preferred suppliers default.
2. Reduce **rate leakage** between negotiated rates and paid prices.
3. Give category managers a trusted cube they open weekly without analyst tickets.
4. Make the platform **AI-ready** without sacrificing metric governance.

## Now (v1 — this repo)

| Use case | Persona | Value |
|---|---|---|
| Executive spend pulse | CPO / Finance | One version of Direct/Indirect spend |
| Compliance & maverick | Category leads | Target off-contract behavior |
| Leakage & should-cost | Strategic Sourcing | Negotiation pipeline $ |
| Supplier risk | Supplier Mgmt | Concentration + performance risk |
| Semantic Q&A | Power users | Self-serve without SQL |

## Next (v1.5 — 90 days)

- Power BI / Fabric semantic model twin of `semantic_layer.yaml`
- Contract expiry early-warning mart
- Savings waterfall tied to initiative IDs (Finance-approved baseline)
- Buyer scorecards (PO price adherence)
- SCD2 supplier master history

## Later (v2 — 6–12 months)

- LLM agents with tool access to semantic metrics only (no free-SQL)
- Invoice OCR → category classification ML
- Should-cost refresh from commodity indices
- Near-real-time PO price checks at requisition
- External risk feeds (financial distress, geo disruption)

## Prioritization rubric

Score epics on: **$ impact × decision frequency × data readiness × adoption ease**.

Reject vanity dashboards that don’t change a sourcing or finance rhythm.

## Adoption plan

1. Embed dashboard link in monthly category operating review template.
2. Train category teams with playbooks (`docs/PLAYBOOKS.md`) — 45-min hands-on.
3. Freeze metric definitions quarterly with Finance (savings baseline governance).
4. Collect enhancement requests → roadmap grooming biweekly.