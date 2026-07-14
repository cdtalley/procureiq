"""ProcureIQ Streamlit analytics product."""

from __future__ import annotations

import os
from typing import Any

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "procureiq-dev-key")


def api_get(path: str, params: dict | None = None) -> Any:
    with httpx.Client(timeout=60.0) as client:
        r = client.get(
            f"{API_BASE}{path}",
            headers={"X-API-Key": API_KEY},
            params=params or {},
        )
        r.raise_for_status()
        return r.json()


def api_post(path: str, payload: dict) -> Any:
    with httpx.Client(timeout=90.0) as client:
        r = client.post(
            f"{API_BASE}{path}",
            headers={"X-API-Key": API_KEY},
            json=payload,
        )
        r.raise_for_status()
        return r.json()


def money(x: float) -> str:
    if pd.isna(x):
        return "—"
    ax = abs(x)
    if ax >= 1e6:
        return f"${x/1e6:,.2f}M"
    if ax >= 1e3:
        return f"${x/1e3:,.1f}K"
    return f"${x:,.0f}"


st.set_page_config(
    page_title="ProcureIQ | Procurement Analytics",
    page_icon="📊",
    layout="wide",
)

st.title("ProcureIQ")
st.caption(
    "AI-ready procurement spend platform — spend cube · PVM · leakage · TCO · semantic agent"
)

try:
    metrics = api_get("/metrics/executive")
except Exception as exc:  # noqa: BLE001
    st.error(
        f"Cannot reach API at `{API_BASE}`. Start Postgres + API, then reseed.\n\n{exc}"
    )
    st.code(
        "docker compose up -d db\n"
        "pip install -r requirements.txt\n"
        "python -m etl.seed\n"
        "uvicorn api.main:app --reload --port 8000\n"
        "streamlit run dashboard/app.py",
        language="bash",
    )
    st.stop()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Spend", money(metrics["total_spend"]))
yoy = metrics.get("yoy_change_pct")
c2.metric("MoM/YoY proxy", f"{yoy:.1f}%" if yoy is not None else "n/a")
c3.metric("Contract Compliance", f"{metrics['contract_compliance_pct']:.1f}%")
c4.metric("Rate Leakage", money(metrics["rate_leakage"]))
c5.metric("Maverick Spend", money(metrics["maverick_spend"]))
c6.metric("Suppliers / Txns", f"{metrics['supplier_count']} / {metrics['transaction_count']:,}")

tab_exec, tab_cube, tab_leak, tab_agent = st.tabs(
    ["Executive Summary", "Category Drill-down", "Price Variance / Leakage", "Ask ProcureIQ"]
)

with tab_exec:
    monthly = pd.DataFrame(api_get("/analytics/executive-monthly")["rows"])
    if not monthly.empty:
        monthly["period_month"] = pd.to_datetime(monthly["period_month"])
        fig = px.area(
            monthly,
            x="period_month",
            y=["direct_spend", "indirect_spend"],
            title="Direct vs Indirect Spend",
            labels={"value": "USD", "period_month": "Month", "variable": "Type"},
        )
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.line(
            monthly,
            x="period_month",
            y=["rate_leakage", "maverick_spend"],
            title="Leakage & Maverick Trajectory",
        )
        st.plotly_chart(fig2, use_container_width=True)

    pvm = pd.DataFrame(api_get("/analytics/pvm")["rows"])
    if not pvm.empty:
        st.subheader("Price–Volume–Mix (latest month)")
        bridge = pd.DataFrame(
            {
                "component": ["Price", "Volume", "Mix"],
                "usd": [
                    pvm["price_effect"].sum(),
                    pvm["volume_effect"].sum(),
                    pvm["mix_effect"].sum(),
                ],
            }
        )
        st.plotly_chart(
            px.bar(bridge, x="component", y="usd", title="PVM Bridge", text="usd"),
            use_container_width=True,
        )
        st.dataframe(pvm, use_container_width=True)

    tco = pd.DataFrame(api_get("/analytics/tco")["rows"])
    if not tco.empty:
        st.subheader("TCO by Supplier")
        st.plotly_chart(
            px.bar(tco.head(12), x="supplier_name", y="tco", color="risk_tier"),
            use_container_width=True,
        )

with tab_cube:
    dio = st.selectbox("Spend type", ["All", "Direct", "Indirect"])
    params = {}
    if dio != "All":
        params["direct_or_indirect"] = dio
    cube = pd.DataFrame(api_get("/analytics/spend-cube", params)["rows"])
    if not cube.empty:
        fig = px.treemap(
            cube,
            path=["direct_or_indirect", "parent_category", "category_name"],
            values="spend",
            title="Spend Cube Hierarchy",
            color="spend",
            color_continuous_scale="Teal",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(cube, use_container_width=True, height=420)

with tab_leak:
    leak = pd.DataFrame(api_get("/analytics/price-variance", {"flagged_only": True})["rows"])
    st.write("Transactions where actual rate exceeds negotiated rate by **> 5%**.")
    if not leak.empty:
        top = (
            leak.groupby("supplier_name", as_index=False)["leakage_amount"]
            .sum()
            .sort_values("leakage_amount", ascending=False)
            .head(15)
        )
        st.plotly_chart(
            px.bar(top, x="supplier_name", y="leakage_amount", title="Top Leakage Suppliers"),
            use_container_width=True,
        )
        st.dataframe(leak, use_container_width=True, height=420)
    dq = pd.DataFrame(api_get("/dq"))
    st.subheader("ETL data quality")
    st.dataframe(dq, use_container_width=True)

with tab_agent:
    st.write(
        "Natural-language questions resolve against **semantic views only** "
        "(not raw tables). SQL is always returned for auditability."
    )
    examples = [
        "What is our total spend?",
        "Which suppliers had the biggest price variance?",
        "Show maverick spend",
        "Explain price volume mix",
        "Which suppliers have the highest TCO?",
        "Top suppliers by spend",
    ]
    choice = st.selectbox("Examples", examples)
    custom = st.text_input("Or ask your own", value="")
    question = custom.strip() or choice
    if st.button("Ask agent", type="primary"):
        with st.spinner("Querying semantic layer…"):
            result = api_post("/agent/ask", {"question": question})
        st.info(result["answer"])
        st.caption(f"Intent: `{result['intent']}` · Mode: `{result['mode']}`")
        st.code(result["sql"], language="sql")
        st.dataframe(pd.DataFrame(result["rows"]), use_container_width=True)
