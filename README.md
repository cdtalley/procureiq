# ProcureIQ

**AI-ready procurement analytics platform** — data infrastructure, spend products, and a semantic layer that BI tools and LLM agents share.

Published repo: [github.com/cdtalley/procureiq](https://github.com/cdtalley/procureiq)

Built for the **Procurement Analytics, Data Infrastructure & Data Products Manager** profile: hands-on builder with a product mindset — cubes, leakage/TCO/PVM, finance-aligned narratives, offshore-ready ETL contracts, and an AI-ready semantic foundation.

```
Synthetic ERP extracts
        ↓  etl/seed + DQ gates
 PostgreSQL star schema (supplier · category · contract · spend)
        ↓  semantic/* SQL views  ←── single contract
        ├──────────────────────────┤
   FastAPI / Power BI twin      LangGraph agent (NL → SQL)
        ↓
   Streamlit decision product
```

---

## Why ProcureIQ (not a notebook dump)

| Capability | Implementation |
|---|---|
| Spend cubes | `semantic.v_spend_cube` — supplier × category × period |
| Price variance / leakage | `semantic.v_price_variance` — flagged when variance **> 5%** |
| TCO | `semantic.v_tco_by_supplier` — spend + risk/quality + switching |
| Volume / rate / mix | `semantic.v_pvm_monthly` |
| Maverick spend | `semantic.v_maverick_spend` — outside approved contracts |
| AI-ready foundation | Agent queries **semantic views only**; SQL returned for audit |
| Production hardening | API key auth, structured JSON logs, ETL DQ checks |

The semantic layer **decouples** dashboards from the AI agent: both consume the same governed views. The agent never free-SQL against raw `fact_*` / `dim_*` tables.

---

## Stack

Python · FastAPI · PostgreSQL · SQLAlchemy · LangGraph · Streamlit · pandas · Docker

---

## Quick start

### Option A — Docker Compose (API + DB + dashboard)

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000/docs  
- Dashboard: http://localhost:8501  
- Seed inside API container (first time):

```bash
docker compose exec api python -m etl.seed
```

### Option B — Local (recommended for iteration)

```bash
cp .env.example .env
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt

docker compose up -d db           # Postgres only
python -m etl.seed                # create tables, load data, apply views, run DQ
uvicorn api.main:app --reload --port 8000
streamlit run dashboard/app.py
```

Default API key: `procureiq-dev-key` (header `X-API-Key`).  
Optional: set `OPENAI_API_KEY` for LLM intent routing via LangGraph; without it, a deterministic router runs (demo always works).

---

## Repository layout

```
etl/                 seed + data quality gates
api/                 FastAPI app, SQLAlchemy models, auth, logging
semantic/            SQL views (the BI ↔ AI contract) + apply helper
agent/               LangGraph / deterministic NL→SQL over semantic views
dashboard/           Streamlit product UI
docker-compose.yml   Postgres + API + dashboard
docs/                Architecture & interview narrative
```

---

## Data model (star schema)

- **dim_supplier** — name, primary category family, risk tier, region  
- **dim_category** — hierarchy + Direct/Indirect  
- **dim_contract** — negotiated rate, term window, supplier link  
- **fact_spend** — PO/invoice grain with negotiated vs actual rate, quantity, cost center, maverick flag  

Seed defaults: **50** suppliers · **10** categories · **220** contracts · **5,500+** transactions over **18** months, with deliberate >5% rate leakage and maverick POs.

---

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/metrics/executive` | KPI cards |
| GET | `/analytics/spend-cube` | Cube rows |
| GET | `/analytics/price-variance` | Leakage |
| GET | `/analytics/pvm` | Price/volume/mix |
| GET | `/analytics/tco` | Supplier TCO |
| GET | `/dq` | Latest ETL quality results |
| POST | `/agent/ask` | `{ "question": "..." }` → answer + SQL + rows |

All analytics/agent routes require header: `X-API-Key: <key>`.

---

## Dashboard tabs

1. **Executive Summary** — Direct/Indirect trend, leakage, PVM bridge, TCO  
2. **Category Drill-down** — spend cube treemap + filters  
3. **Price Variance / Leakage** — >5% flags + DQ panel  
4. **Ask ProcureIQ** — chat wired to the semantic agent  

---

## Architecture note (semantic as contract)

```
BI / Streamlit  ──SELECT──▶  semantic.v_*  ◀──tool──  LangGraph agent
                              ▲
                     ETL publishes & DQ gates
                              ▲
                     dim_* + fact_spend
```

If a metric is not in the semantic layer, neither BI nor AI can invent it. That is the “AI-ready data structure” design: **governed products first, LLM second**.

---

## Role-fit resume bullet

> Built **ProcureIQ**, an AI-ready procurement analytics platform: PostgreSQL star schema, governed semantic spend cube (leakage, TCO, PVM, maverick), FastAPI data products with API-key auth & DQ gates, Streamlit executive UI, and a LangGraph agent that answers natural-language questions strictly against semantic views with auditable SQL.

---

## Tests

```bash
pytest -q
```
