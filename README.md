# ProcureIQ

**Procurement analytics platform · data infrastructure · decision products**

Portfolio build for the **Procurement Analytics, Data Infrastructure & Data Products Manager** role: a hands-on, product-owned lakehouse that turns Direct/Indirect spend into governed cubes, finance-aligned variance, leakage/should-cost/TCO products, and an AI-ready semantic layer.

```
CSV land (PO · Invoice · Contract · MDM · GL · Should-cost)
        ↓  bronze → silver (DQ) → gold (star + marts)
        ↓  analytics (PVM · leakage · TCO · opportunity)
        ↓  ML (supplier risk · anomaly) + semantic Q&A
        ↓  Streamlit decision product  ↔  Fabric / Power BI twin path
```

---

## Why this exists (role fit)

This is not a notebook dump. It is how I would run the function:

| JD responsibility | What ProcureIQ proves |
|---|---|
| **Data infrastructure & architecture** | End-to-end medallion pipeline; dimensional spend grain; YAML orchestration contract for dotted-line delivery |
| **Analytical cubes** | Supplier × category × contract × volume × rate × spend hierarchies (`gold.spend_cube`, category/supplier marts) |
| **Single source of truth** | POs, invoices, contracts, finance actuals, should-cost joined into `gold.fact_spend` |
| **Master data governance** | Supplier completeness, category taxonomy, duplicate flags in `silver.data_quality_results` |
| **Spend / financial / should-cost** | PVM (price–volume–mix), rate leakage, should-cost gap, TCO, budget/forecast/actual mart |
| **Dashboards & self-serve** | Executive Streamlit product + playbooks; semantic NL → governed SQL (LLM-ready) |
| **Offshore / platform partnership** | `configs/pipeline.yaml` as the build contract; design ownership retained locally |
| **Product ownership & enablement** | Roadmap, persona use cases, category playbooks for operating rhythms |
| **Future-ready / AI** | `configs/semantic_layer.yaml` + Isolation Forest anomalies + composite supplier risk |

**Stack (portable):** Python · DuckDB · SQL star schema · scikit-learn · Streamlit/Plotly · YAML semantic layer  
**Enterprise landing path:** Microsoft Fabric / Power BI semantic model, Snowflake, Databricks, AWS analytics.

---

## Quick start

```bash
# from repo root
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # macOS/Linux

pip install -r requirements.txt
python run_all.py                 # generate → ETL → analytics → ML
streamlit run src/dashboard/app.py
```

Dashboard opens at **http://localhost:8501**.

Optional: `python run_all.py --skip-generate` to rebuild on existing `data/raw`.  
Optional: `python run_all.py --demo-qa` to print semantic Q&A answers in the terminal.  
Tests: `pytest` (requires warehouse built).

---

## Product surface (dashboard tabs)

| Tab | Decision job |
|---|---|
| **Executive Trend** | Direct vs Indirect pulse; leakage / should-cost / savings trajectory |
| **Spend Cube** | L1→L2→L3 hierarchy treemap colored by rate leakage |
| **PVM Variance** | Price vs volume vs mix effects (Finance narrative for MoM spend change) |
| **Leakage & TCO** | Opportunity stack + TCO uplift + supplier×category leakage |
| **Supplier Risk** | Risk vs spend concentration; Isolation Forest anomalies |
| **Finance Alignment** | Budget / forecast / actual variance by BU |
| **Ask ProcureIQ** | Semantic self-serve — NL intent → governed SQL over marts |

Category operating guides: [`docs/PLAYBOOKS.md`](docs/PLAYBOOKS.md).

---

## Repository map

```
configs/
  pipeline.yaml           # ETL/ELT contract (sources, layers, DQ ownership)
  semantic_layer.yaml     # Metrics & entities for BI + LLM tools
sql/models/gold_views.sql # Additional gold view patterns
src/
  generate_data.py        # Synthetic enterprise sources (safe for portfolio)
  pipelines/              # bronze → silver → gold
  analytics/              # should-cost, leakage/TCO/opportunity, PVM
  ml/                     # supplier risk, anomalies, semantic_qa
  dashboard/app.py        # Analytics product UI
docs/
  ARCHITECTURE.md         # Medallion + dimensional design
  DATA_DICTIONARY.md      # Consumer definitions
  PRODUCT_ROADMAP.md      # Product owner prioritization
  PLAYBOOKS.md            # Enablement for category teams
  INTERVIEW_NARRATIVE.md  # STAR mapping + 8-min demo script
  ONE_PAGER.md            # Hiring-manager skim
data/
  raw/                    # Source extracts
  warehouse/procureiq.duckdb
  exports/                # CSV/Parquet handoffs for BI tools
```

---

## Architecture (short)

**Fact grain:** one row per invoice line in `gold.fact_spend`, conformed to supplier, category, contract, cost center, and calendar dimensions.

**Measures that matter to Procurement + Finance:** invoice spend, on-contract / maverick flags, price variance (rate leakage), should-cost gap, savings vs baseline, TCO, PVM price/volume/mix effects, budget variance.

**Governance:** silver DQ gates block null master keys, validate category hierarchy, and queue potential supplier duplicates.

**AI-ready:** semantic metrics defined once; `src/ml/semantic_qa.py` routes NL → intent → SQL. Swap the router for an LLM tool-caller without changing marts.

Full detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Demo script (8 minutes)

1. Architecture — multi-source → medallion → products  
2. Executive metrics — spend, compliance, leakage, maverick  
3. Spend cube treemap — hierarchy + leakage color  
4. **PVM** — why MoM spend moved (rate vs volume vs mix)  
5. Opportunity stack — playbook-linked dollars  
6. Supplier risk scatter — commercial + ops concentration  
7. Ask ProcureIQ — “Where are the biggest savings opportunities?”  
8. Close — governed infrastructure, decision products, AI-ready semantic layer

Longer interview map: [`docs/INTERVIEW_NARRATIVE.md`](docs/INTERVIEW_NARRATIVE.md).

---

## Resume / LinkedIn bullet (adapt)

> Built **ProcureIQ**, an end-to-end procurement analytics platform: medallion DuckDB lakehouse, dimensional spend cube, PVM / should-cost / TCO / leakage marts, finance budget alignment, supplier risk & anomaly models, and a governed semantic self-serve layer for Direct/Indirect spend decisioning — transferable to Microsoft Fabric / Power BI.

---

## Design principles

1. One version of spend before any dashboard.  
2. Every gold/analytics table answers a named use case.  
3. Metrics defined once (YAML) for BI and LLM.  
4. Cloud-portable SQL — local DuckDB today; Fabric Warehouse / Snowflake tomorrow.  
5. Product > project — roadmap, playbooks, and adoption rhythms included.

Synthetic data only. Production would add RLS by BU, PII vaulting, and audited semantic prompts.
