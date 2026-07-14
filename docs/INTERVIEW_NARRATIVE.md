# Interview Narrative — Map Your Experience to This JD

Use ProcureIQ as the **proof artifact**. Pair it with real career STAR stories.

## Positioning statement

> I’m an AI engineer / data scientist who builds *procurement decision systems*, not notebooks. ProcureIQ shows I can own the full stack this role requires: infrastructure & modeling, financial analytics products, self-serve enablement, and an AI-ready semantic foundation — with a product owner mindset.

## STAR stories you can tell with this repo

### 1) Data infrastructure & single source of truth
**Situation:** Spend lived in AP, POs, and contracts with conflicting totals.  
**Task:** Build a governed spend fact as the enterprise source of truth.  
**Action:** Medallion pipeline; invoice grain; contract/PO/should-cost joins; DQ gates on MDM.  
**Result:** Demo shows one executive number + drill to supplier/category; duplicate supplier flagged for stewardship.

### 2) Leakage & should-cost (sourcing $ impact)
**Situation:** Negotiated rates not showing up in paid prices; Finance questioned savings.  
**Task:** Quantify rate leakage vs should-cost vs maverick.  
**Action:** Opportunity stack mart + playbooks; separate realized savings from leakage headwinds.  
**Result:** Clear $ prioritization for category managers (what to attack first).

### 3) Product ownership & adoption
**Situation:** Prior dashboards unused after launch.  
**Task:** Ship an analytics *product* tied to operating rhythms.  
**Action:** Roadmap, persona-based tabs, training playbooks, semantic self-serve.  
**Result:** Artifact demonstrates how you’d run dotted-line delivery and business enablement.

### 4) AI-ready foundation (your unfair edge)
**Situation:** Leadership wants AI in procurement without chaotic answers.  
**Task:** Design for ML/LLM on trusted metrics.  
**Action:** YAML semantic layer; NL→SQL intents; Isolation Forest anomalies; composite supplier risk.  
**Result:** “AI on top of governed data products” — exactly what *Future-Ready Data Foundation* asks for.

## Likely interview questions → your answer anchors

| Question | Anchor |
|---|---|
| How do you model spend? | Invoice fact grain; dims for supplier/category/contract/CC/calendar; cube aggregates |
| Direct vs Indirect? | `category_l1` / `spend_type` partition throughout marts |
| How do you partner with Finance? | Budget/forecast/actual mart; savings baseline discipline |
| Power BI vs what you built? | Same semantic patterns; Streamlit for portable portfolio demo; happy to twin in Fabric |
| How do you lead offshore? | Pipeline YAML + DQ contracts + review gates; you own design & acceptance |
| What’s first 90 days on the job? | Discovery on source systems → metric dictionary with Finance → MVP compliance/leakage cube → adoption |

## Demo script (8 minutes)

1. **Architecture slide** (30s) — multi-source → medallion → products  
2. **Executive metrics** (90s) — spend, compliance, leakage, maverick  
3. **Spend cube treemap** (90s) — hierarchy + leakage color  
4. **Opportunity stack** (90s) — playbook-linked $  
5. **Supplier risk scatter** (60s) — commercial + ops risk  
6. **Ask ProcureIQ** (90s) — “Where are the biggest savings opportunities?”  
7. **Close** (30s) — “This is how I’d run the function: governed infrastructure, decision products, AI-ready semantic layer.”

## Resume bullet (adapt)

- Built **ProcureIQ**, an end-to-end procurement analytics platform: medallion DuckDB lakehouse, dimensional spend cube, PVM/should-cost/TCO marts, supplier risk & anomaly models, and a governed semantic self-serve layer for Direct/Indirect spend decisioning.