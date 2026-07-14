"""ProcureIQ FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from agent.graph import ask
from api.auth import require_api_key
from api.db import Base, engine, get_db, wait_for_db
from api.logging_setup import configure_logging, get_logger
from api.schemas import AgentAskIn, AgentAskOut, DQCheckOut, HealthOut, MetricCard
from api.serialize import jsonable_rows

configure_logging()
log = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    log.info("api_started", service="procureiq")
    yield


app = FastAPI(
    title="ProcureIQ API",
    description="Procurement analytics data products — semantic layer + AI agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@app.get("/metrics/executive", response_model=MetricCard, dependencies=[Depends(require_api_key)])
def executive_metrics(db: Session = Depends(get_db)) -> MetricCard:
    row = db.execute(
        text(
            """
            select
                coalesce(sum(total_spend), 0) as total_spend,
                coalesce(sum(rate_leakage), 0) as rate_leakage,
                coalesce(sum(maverick_spend), 0) as maverick_spend
            from semantic.v_executive_monthly
            """
        )
    ).mappings().one()
    months = db.execute(
        text(
            """
            select period_month, total_spend
            from semantic.v_executive_monthly
            order by period_month
            """
        )
    ).mappings().all()
    yoy = None
    if len(months) >= 13:
        latest = float(months[-1]["total_spend"])
        prior = float(months[-13]["total_spend"])
        if prior:
            yoy = round((latest - prior) / prior * 100, 2)
    compliance = db.execute(
        text(
            """
            select
              100.0 * sum(case when contract_id is not null then invoice_amount else 0 end)
              / nullif(sum(case when invoice_amount >= 0 then invoice_amount else 0 end), 0)
            from fact_spend
            """
        )
    ).scalar()
    suppliers = db.execute(text("select count(*) from dim_supplier")).scalar()
    txns = db.execute(
        text("select count(*) from fact_spend where invoice_amount >= 0")
    ).scalar()
    return MetricCard(
        total_spend=float(row["total_spend"]),
        yoy_change_pct=yoy,
        contract_compliance_pct=round(float(compliance or 0), 2),
        rate_leakage=float(row["rate_leakage"]),
        maverick_spend=float(row["maverick_spend"]),
        supplier_count=int(suppliers or 0),
        transaction_count=int(txns or 0),
    )


@app.get("/analytics/spend-cube", dependencies=[Depends(require_api_key)])
def spend_cube(
    db: Session = Depends(get_db),
    direct_or_indirect: str | None = None,
    limit: int = Query(default=200, le=2000),
):
    clauses = []
    params: dict = {"limit": limit}
    if direct_or_indirect:
        clauses.append("direct_or_indirect = :dio")
        params["dio"] = direct_or_indirect
    where = f"where {' and '.join(clauses)}" if clauses else ""
    sql = f"""
        select period_month, supplier_name, category_name, parent_category,
               direct_or_indirect, cost_center, txn_count, volume, spend
        from semantic.v_spend_cube
        {where}
        order by spend desc
        limit :limit
    """
    rows = db.execute(text(sql), params).mappings().all()
    return {"rows": jsonable_rows(rows)}


@app.get("/analytics/price-variance", dependencies=[Depends(require_api_key)])
def price_variance(db: Session = Depends(get_db), flagged_only: bool = True, limit: int = 100):
    sql = """
        select spend_date, supplier_name, category_name, po_number,
               negotiated_rate, actual_rate, variance_pct, leakage_amount, variance_flag
        from semantic.v_price_variance
        where (:flagged_only = false or variance_flag)
        order by leakage_amount desc nulls last
        limit :limit
    """
    rows = db.execute(
        text(sql), {"flagged_only": flagged_only, "limit": limit}
    ).mappings().all()
    return {"rows": jsonable_rows(rows)}


@app.get("/analytics/executive-monthly", dependencies=[Depends(require_api_key)])
def executive_monthly(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            select period_month, total_spend, direct_spend, indirect_spend,
                   rate_leakage, maverick_spend, txn_count
            from semantic.v_executive_monthly
            order by period_month
            """
        )
    ).mappings().all()
    return {"rows": jsonable_rows(rows)}


@app.get("/analytics/pvm", dependencies=[Depends(require_api_key)])
def pvm(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            select category_name, direct_or_indirect, spend, spend_change,
                   price_effect, volume_effect, mix_effect
            from semantic.v_pvm_monthly
            where period_month = (select max(period_month) from semantic.v_pvm_monthly)
            order by abs(spend_change) desc
            limit 20
            """
        )
    ).mappings().all()
    return {"rows": jsonable_rows(rows)}


@app.get("/analytics/tco", dependencies=[Depends(require_api_key)])
def tco(db: Session = Depends(get_db), limit: int = 25):
    rows = db.execute(
        text(
            """
            select supplier_name, risk_tier, region, invoice_spend,
                   risk_quality_cost, switching_cost_est, tco
            from semantic.v_tco_by_supplier
            order by tco desc
            limit :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return {"rows": jsonable_rows(rows)}


@app.get("/dq", response_model=list[DQCheckOut], dependencies=[Depends(require_api_key)])
def dq_results(db: Session = Depends(get_db)) -> list[DQCheckOut]:
    rows = db.execute(
        text(
            """
            select check_name, status, row_count, detail
            from data_quality_results
            order by id
            """
        )
    ).mappings().all()
    return [DQCheckOut(**dict(r)) for r in rows]


@app.post("/agent/ask", response_model=AgentAskOut, dependencies=[Depends(require_api_key)])
def agent_ask(body: AgentAskIn, db: Session = Depends(get_db)) -> AgentAskOut:
    log.info("agent_ask", question=body.question)
    result = ask(db, body.question)
    return AgentAskOut(
        question=result.question,
        answer=result.answer,
        sql=result.sql,
        intent=result.intent,
        rows=result.rows,
        mode=result.mode,
    )
