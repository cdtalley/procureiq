"""LangGraph / deterministic NL→SQL agent over ProcureIQ semantic views only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, TypedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings


ALLOWED_VIEWS = {
    "semantic.v_spend_cube",
    "semantic.v_price_variance",
    "semantic.v_tco_by_supplier",
    "semantic.v_maverick_spend",
    "semantic.v_executive_monthly",
    "semantic.v_pvm_monthly",
}


class AgentState(TypedDict, total=False):
    question: str
    intent: str
    sql: str
    rows: list[dict[str, Any]]
    answer: str
    mode: str


@dataclass
class AgentResult:
    question: str
    intent: str
    sql: str
    answer: str
    rows: list[dict[str, Any]]
    mode: str


INTENT_SQL: dict[str, tuple[str, str]] = {
    "total_spend": (
        "total_spend",
        """
        select round(sum(total_spend)::numeric, 2) as total_spend,
               round(sum(direct_spend)::numeric, 2) as direct_spend,
               round(sum(indirect_spend)::numeric, 2) as indirect_spend
        from semantic.v_executive_monthly
        """,
    ),
    "leakage": (
        "price_variance",
        """
        select supplier_name, category_name,
               round(sum(leakage_amount)::numeric, 2) as leakage_amount,
               round(avg(variance_pct)::numeric, 2) as avg_variance_pct,
               count(*) as flagged_txns
        from semantic.v_price_variance
        where variance_flag
        group by 1, 2
        order by leakage_amount desc
        limit 15
        """,
    ),
    "maverick": (
        "maverick",
        """
        select supplier_name, category_name,
               round(sum(spend)::numeric, 2) as maverick_spend,
               count(*) as txn_count
        from semantic.v_maverick_spend
        group by 1, 2
        order by maverick_spend desc
        limit 15
        """,
    ),
    "tco": (
        "tco",
        """
        select supplier_name, risk_tier, invoice_spend, risk_quality_cost,
               switching_cost_est, tco
        from semantic.v_tco_by_supplier
        order by tco desc
        limit 15
        """,
    ),
    "pvm": (
        "pvm",
        """
        select
            round(sum(price_effect)::numeric, 2) as price_effect,
            round(sum(volume_effect)::numeric, 2) as volume_effect,
            round(sum(mix_effect)::numeric, 2) as mix_effect,
            round(sum(spend_change)::numeric, 2) as spend_change
        from semantic.v_pvm_monthly
        where period_month = (select max(period_month) from semantic.v_pvm_monthly)
        """,
    ),
    "top_suppliers": (
        "top_suppliers",
        """
        select supplier_name, risk_tier, region,
               round(sum(spend)::numeric, 2) as spend
        from semantic.v_spend_cube
        group by 1, 2, 3
        order by spend desc
        limit 10
        """,
    ),
    "category": (
        "category",
        """
        select category_name, direct_or_indirect,
               round(sum(spend)::numeric, 2) as spend
        from semantic.v_spend_cube
        group by 1, 2
        order by spend desc
        limit 15
        """,
    ),
    "executive": (
        "executive_trend",
        """
        select period_month, total_spend, direct_spend, indirect_spend,
               rate_leakage, maverick_spend
        from semantic.v_executive_monthly
        order by period_month
        """,
    ),
}

INTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("leakage", re.compile(r"leakage|price variance|paid above|over.?paid|variance", re.I)),
    ("maverick", re.compile(r"maverick|off[- ]?contract|non[- ]?po|outside.*contract", re.I)),
    ("tco", re.compile(r"\btco\b|total cost of ownership|switching cost", re.I)),
    ("pvm", re.compile(r"\bpvm\b|price.?volume.?mix|volume effect|mix effect", re.I)),
    ("top_suppliers", re.compile(r"top suppliers|largest suppliers|biggest suppliers", re.I)),
    ("category", re.compile(r"by category|category spend|spend by category", re.I)),
    ("executive", re.compile(r"trend|monthly|executive|over time|yoy|year over", re.I)),
    ("total_spend", re.compile(r"total spend|how much.*(spend|spent)|overall spend", re.I)),
]


def resolve_intent(question: str) -> str:
    for name, pattern in INTENT_PATTERNS:
        if pattern.search(question):
            return name
    return "total_spend"


def _assert_semantic_only(sql: str) -> None:
    lowered = sql.lower()
    if "information_schema" in lowered or "pg_catalog" in lowered:
        raise ValueError("Catalog queries are not allowed")
    # Must reference at least one semantic view; block raw base tables as FROM targets
    if "semantic." not in lowered:
        raise ValueError("Agent may only query semantic.* views")
    forbidden = re.findall(
        r"\b(from|join)\s+(dim_|fact_|data_quality)",
        lowered,
    )
    if forbidden:
        raise ValueError("Agent must not query base tables directly")


def execute_sql(session: Session, sql: str) -> list[dict[str, Any]]:
    _assert_semantic_only(sql)
    result = session.execute(text(sql))
    cols = list(result.keys())
    return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]


def narrate(intent: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No rows returned for this question against the semantic layer."
    r0 = rows[0]
    if intent == "total_spend":
        return (
            f"Enterprise invoice spend is ${float(r0['total_spend']):,.0f} "
            f"(Direct ${float(r0['direct_spend']):,.0f} / Indirect ${float(r0['indirect_spend']):,.0f})."
        )
    if intent == "leakage":
        return (
            f"Largest leakage: {r0['supplier_name']} / {r0['category_name']} "
            f"at ${float(r0['leakage_amount']):,.0f} across {r0['flagged_txns']} flagged txns."
        )
    if intent == "maverick":
        return (
            f"Top maverick pocket: {r0['supplier_name']} "
            f"(${float(r0['maverick_spend']):,.0f})."
        )
    if intent == "tco":
        return f"Highest TCO supplier is {r0['supplier_name']} at ${float(r0['tco']):,.0f}."
    if intent == "pvm":
        return (
            f"Latest MoM Δ ${float(r0['spend_change']):,.0f} = "
            f"price ${float(r0['price_effect']):,.0f} + volume ${float(r0['volume_effect']):,.0f} "
            f"+ mix ${float(r0['mix_effect']):,.0f}."
        )
    if intent == "top_suppliers":
        return f"Largest supplier by spend: {r0['supplier_name']} (${float(r0['spend']):,.0f})."
    if intent == "category":
        return f"Largest category: {r0['category_name']} (${float(r0['spend']):,.0f})."
    return f"Returned {len(rows)} rows from the semantic layer."


def run_deterministic(session: Session, question: str) -> AgentResult:
    intent = resolve_intent(question)
    _, sql = INTENT_SQL[intent]
    sql = sql.strip()
    rows = execute_sql(session, sql)
    # Convert Decimals / dates for JSON
    clean = [_serialize_row(r) for r in rows]
    return AgentResult(
        question=question,
        intent=intent,
        sql=sql,
        answer=narrate(intent, clean),
        rows=clean,
        mode="deterministic",
    )


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif hasattr(v, "__float__") and not isinstance(v, bool):
            try:
                out[k] = float(v)
            except Exception:  # noqa: BLE001
                out[k] = v
        else:
            out[k] = v
    return out


def run_llm_graph(session: Session, question: str) -> AgentResult:
    """LangGraph path: LLM picks intent, then we execute curated semantic SQL."""
    from langgraph.graph import END, StateGraph
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=settings.openai_api_key)
    intents = ", ".join(INTENT_SQL.keys())

    def choose_intent(state: AgentState) -> AgentState:
        msg = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are the ProcureIQ routing brain. "
                        f"Choose exactly one intent from: {intents}. "
                        "Reply with only the intent key."
                    )
                ),
                HumanMessage(content=state["question"]),
            ]
        )
        raw = str(msg.content).strip().lower().replace("`", "").split()[0]
        intent = raw if raw in INTENT_SQL else resolve_intent(state["question"])
        _, sql = INTENT_SQL[intent]
        return {**state, "intent": intent, "sql": sql.strip(), "mode": "llm"}

    def run_query(state: AgentState) -> AgentState:
        rows = [_serialize_row(r) for r in execute_sql(session, state["sql"])]
        return {**state, "rows": rows}

    def write_answer(state: AgentState) -> AgentState:
        answer = narrate(state["intent"], state.get("rows") or [])
        return {**state, "answer": answer}

    graph = StateGraph(AgentState)
    graph.add_node("choose_intent", choose_intent)
    graph.add_node("run_query", run_query)
    graph.add_node("write_answer", write_answer)
    graph.set_entry_point("choose_intent")
    graph.add_edge("choose_intent", "run_query")
    graph.add_edge("run_query", "write_answer")
    graph.add_edge("write_answer", END)
    app = graph.compile()
    final = app.invoke({"question": question})
    return AgentResult(
        question=question,
        intent=final["intent"],
        sql=final["sql"],
        answer=final["answer"],
        rows=final.get("rows") or [],
        mode=final.get("mode", "llm"),
    )


def ask(session: Session, question: str) -> AgentResult:
    if settings.openai_api_key:
        try:
            return run_llm_graph(session, question)
        except Exception:  # noqa: BLE001 — always fall back for portfolio demos
            return run_deterministic(session, question)
    return run_deterministic(session, question)
