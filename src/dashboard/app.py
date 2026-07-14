"""
ProcureIQ Executive Analytics Product - Streamlit.

Maps to JD: spend cubes, compliance, leakage, TCO, supplier performance,
finance alignment, and AI-assisted self-serve Q&A.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ml.semantic_qa import ask
from src.paths import WAREHOUSE_DB

st.set_page_config(
    page_title="ProcureIQ | Procurement Analytics",
    page_icon="📊",
    layout="wide",
)


@st.cache_resource
def get_con():
    if not WAREHOUSE_DB.exists():
        return None
    return duckdb.connect(str(WAREHOUSE_DB), read_only=True)


def q(sql: str) -> pd.DataFrame:
    con = get_con()
    if con is None:
        return pd.DataFrame()
    return con.execute(sql).df()


def money(x: float) -> str:
    if pd.isna(x):
        return "-"
    ax = abs(x)
    if ax >= 1e6:
        return f"${x/1e6:,.2f}M"
    if ax >= 1e3:
        return f"${x/1e3:,.1f}K"
    return f"${x:,.0f}"


def main() -> None:
    st.title("ProcureIQ")
    st.caption(
        "Procurement analytics data product — spend cube · PVM · compliance · "
        "should-cost · TCO · supplier risk · semantic self-serve"
    )

    if not WAREHOUSE_DB.exists():
        st.error(
            "Warehouse not found. From the procureiq root run:\n\n"
            "`python -m src.generate_data && python -m src.pipelines.run_pipeline && "
            "python -m src.analytics.should_cost && python -m src.analytics.variance && "
            "python -m src.ml.anomaly_risk`"
        )
        return

    monthly = q("select * from gold.mart_monthly_executive order by period_month")
    if monthly.empty:
        st.warning("Gold marts are empty - re-run the pipeline.")
        return

    total_spend = float(monthly["total_spend"].sum())
    leakage = float(monthly["rate_leakage"].sum())
    maverick = float(monthly["maverick_spend"].sum())
    compliance = float(
        monthly["on_contract_spend"].sum() / monthly["total_spend"].sum() * 100
    )
    savings = float(monthly["savings_realized"].sum())
    should_gap = float(monthly["should_cost_gap"].sum())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Spend", money(total_spend))
    c2.metric("Contract Compliance", f"{compliance:.1f}%")
    c3.metric("Rate Leakage", money(leakage))
    c4.metric("Should-Cost Gap", money(should_gap))
    c5.metric("Maverick Spend", money(maverick))
    c6.metric("Savings Realized", money(savings))

    tab_overview, tab_cube, tab_pvm, tab_leakage, tab_suppliers, tab_finance, tab_ai = st.tabs(
        [
            "Executive Trend",
            "Spend Cube",
            "PVM Variance",
            "Leakage & TCO",
            "Supplier Risk",
            "Finance Alignment",
            "Ask ProcureIQ",
        ]
    )

    with tab_overview:
        m = monthly.copy()
        m["period_month"] = pd.to_datetime(m["period_month"])
        fig = px.area(
            m,
            x="period_month",
            y=["direct_spend", "indirect_spend"],
            title="Direct vs Indirect Spend by Month",
            labels={"value": "Spend (USD)", "period_month": "Month", "variable": "Type"},
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            m,
            x="period_month",
            y=["rate_leakage", "should_cost_gap", "savings_realized"],
            title="Leakage, Should-Cost Gap, and Savings Trajectory",
            labels={"value": "USD", "period_month": "Month", "variable": "Metric"},
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab_cube:
        cat = q(
            """
            select spend_type, category_l2, category_l3, total_spend,
                   rate_leakage, should_cost_gap, contract_compliance_rate, supplier_count
            from gold.mart_category_spend
            order by total_spend desc
            """
        )
        left, right = st.columns([1.2, 1])
        with left:
            fig = px.treemap(
                cat,
                path=["spend_type", "category_l2", "category_l3"],
                values="total_spend",
                title="Spend Cube Hierarchy (L1 -> L2 -> L3)",
                color="rate_leakage",
                color_continuous_scale="RdYlGn_r",
            )
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.dataframe(
                cat.assign(
                    total_spend=lambda d: d["total_spend"].map(money),
                    rate_leakage=lambda d: d["rate_leakage"].map(money),
                    contract_compliance_rate=lambda d: (d["contract_compliance_rate"] * 100).round(1),
                ),
                use_container_width=True,
                height=480,
            )

    with tab_pvm:
        st.caption(
            "Price–Volume–Mix decomposition of MoM spend change — Finance / category "
            "narrative for what drove Direct vs Indirect movement."
        )
        pvm = q(
            """
            select spend_type, category_l3, spend, spend_change,
                   price_effect, volume_effect, mix_effect
            from analytics.pvm_latest_summary
            order by abs(spend_change) desc
            """
        )
        if pvm.empty:
            st.warning("PVM mart empty — run `python -m src.analytics.variance`.")
        else:
            totals = {
                "price_effect": float(pvm["price_effect"].sum()),
                "volume_effect": float(pvm["volume_effect"].sum()),
                "mix_effect": float(pvm["mix_effect"].sum()),
            }
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Price (rate) effect", money(totals["price_effect"]))
            p2.metric("Volume effect", money(totals["volume_effect"]))
            p3.metric("Mix effect", money(totals["mix_effect"]))
            p4.metric("Net MoM spend Δ", money(float(pvm["spend_change"].sum())))

            water = pd.DataFrame(
                {
                    "component": ["Price effect", "Volume effect", "Mix effect"],
                    "usd": [
                        totals["price_effect"],
                        totals["volume_effect"],
                        totals["mix_effect"],
                    ],
                }
            )
            fig = px.bar(
                water,
                x="component",
                y="usd",
                text="usd",
                title="Enterprise PVM Bridge (latest month vs prior)",
                labels={"usd": "USD", "component": "Lever"},
                color="component",
                color_discrete_sequence=["#c45c26", "#2f5d50", "#3d5a80"],
            )
            fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            fig2 = px.bar(
                pvm.head(15),
                x="category_l3",
                y=["price_effect", "volume_effect", "mix_effect"],
                barmode="relative",
                title="Top Categories — Price / Volume / Mix Contribution",
                labels={"value": "USD", "category_l3": "Category", "variable": "Effect"},
                color_discrete_map={
                    "price_effect": "#c45c26",
                    "volume_effect": "#2f5d50",
                    "mix_effect": "#3d5a80",
                },
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(
                pvm.assign(
                    spend=lambda d: d["spend"].map(money),
                    spend_change=lambda d: d["spend_change"].map(money),
                    price_effect=lambda d: d["price_effect"].map(money),
                    volume_effect=lambda d: d["volume_effect"].map(money),
                    mix_effect=lambda d: d["mix_effect"].map(money),
                ),
                use_container_width=True,
                height=400,
            )

    with tab_leakage:
        opp = q("select * from analytics.opportunity order by opportunity_usd desc")
        tco = q("select * from analytics.tco order by tco desc")
        leak = q(
            """
            select supplier_name, category_l3, spend, rate_leakage, should_cost_gap,
                   maverick_spend, leakage_rate_pct
            from analytics.leakage
            order by rate_leakage desc
            limit 25
            """
        )
        st.subheader("Savings Opportunity Stack")
        fig = px.bar(
            opp,
            x="opportunity_type",
            y="opportunity_usd",
            text="opportunity_usd",
            title="Addressable Opportunity by Playbook Lever",
            labels={"opportunity_usd": "USD", "opportunity_type": "Lever"},
        )
        fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(opp, use_container_width=True)

        st.subheader("TCO Uplift by Category")
        fig = px.bar(
            tco.head(12),
            x="category_l3",
            y="tco_uplift",
            color="spend_type",
            title="TCO Uplift Beyond Invoice Price",
            labels={"tco_uplift": "USD", "category_l3": "Category"},
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top Rate Leakage - Supplier × Category")
        st.dataframe(
            leak.assign(
                spend=lambda d: d["spend"].map(money),
                rate_leakage=lambda d: d["rate_leakage"].map(money),
                should_cost_gap=lambda d: d["should_cost_gap"].map(money),
                maverick_spend=lambda d: d["maverick_spend"].map(money),
                leakage_rate_pct=lambda d: (d["leakage_rate_pct"] * 100).round(2),
            ),
            use_container_width=True,
        )

    with tab_suppliers:
        risk = q(
            """
            select supplier_name, supplier_tier, supplier_country, risk_tier,
                   supplier_risk_score, total_spend, rate_leakage,
                   contract_compliance_rate, otd_rate, quality_ppm
            from ml.supplier_risk
            order by supplier_risk_score desc
            """
        )
        fig = px.scatter(
            risk,
            x="total_spend",
            y="supplier_risk_score",
            color="risk_tier",
            size="total_spend",
            hover_name="supplier_name",
            title="Supplier Risk vs Spend Concentration",
            labels={"total_spend": "Spend (USD)", "supplier_risk_score": "Risk Score"},
        )
        st.plotly_chart(fig, use_container_width=True)

        anomalies = q(
            """
            select invoice_id, invoice_date, supplier_id, category_l3,
                   invoice_amount, price_variance, anomaly_score
            from ml.spend_anomalies
            where is_anomaly
            order by anomaly_score desc
            limit 50
            """
        )
        st.subheader("Flagged Spend Anomalies (Isolation Forest)")
        st.dataframe(anomalies, use_container_width=True)
        st.dataframe(
            risk.assign(
                total_spend=lambda d: d["total_spend"].map(money),
                rate_leakage=lambda d: d["rate_leakage"].map(money),
                contract_compliance_rate=lambda d: (d["contract_compliance_rate"] * 100).round(1),
                supplier_risk_score=lambda d: d["supplier_risk_score"].round(3),
            ),
            use_container_width=True,
            height=360,
        )

    with tab_finance:
        fin = q(
            """
            select gl_period, business_unit,
                   sum(actual_amount) as actual,
                   sum(budget_amount) as budget,
                   sum(forecast_amount) as forecast,
                   sum(budget_variance) as budget_variance
            from gold.mart_finance_alignment
            group by 1, 2
            order by 1, 2
            """
        )
        fig = px.bar(
            fin,
            x="gl_period",
            y="budget_variance",
            color="business_unit",
            barmode="group",
            title="Budget Variance by Business Unit (Actual − Budget)",
            labels={"budget_variance": "USD", "gl_period": "GL Period"},
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(fin, use_container_width=True)

    with tab_ai:
        st.subheader("Semantic Self-Serve (LLM-ready)")
        st.write(
            "Questions resolve against the semantic layer -> governed SQL over gold/analytics/ml marts. "
            "Same interface you’d wrap with Fabric Copilot or an LLM tool-caller."
        )
        examples = [
            "What is our total spend?",
            "Show maverick spend",
            "Where is rate leakage highest?",
            "Explain price volume mix",
            "Which suppliers are high risk?",
            "Where are the biggest savings opportunities?",
        ]
        choice = st.selectbox("Example questions", examples)
        custom = st.text_input("Or ask your own", value="")
        question = custom.strip() or choice
        if st.button("Run question", type="primary"):
            result = ask(question)
            st.info(result.answer_text)
            st.code(result.sql, language="sql")
            st.dataframe(pd.DataFrame(result.rows), use_container_width=True)


if __name__ == "__main__":
    main()
