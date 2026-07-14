"""
Semantic-layer NL query engine (LLM-ready).

Resolves natural-language procurement questions against the YAML semantic layer
and DuckDB marts - same pattern as Fabric Copilot / dbt MetricFlow / Looker.
No external LLM required for demo; plugs into an LLM tool-calling layer later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import yaml

from src.paths import CONFIGS, WAREHOUSE_DB


@dataclass
class QueryResult:
    question: str
    intent: str
    sql: str
    answer_text: str
    rows: list[dict]


INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("opportunity", re.compile(r"opportunity|where.*sav(e|ings)|cost reduction|biggest savings", re.I)),
    ("total_spend", re.compile(r"total spend|how much.*(spend|spent)|overall spend", re.I)),
    ("maverick", re.compile(r"maverick|off[- ]?po|non[- ]?po", re.I)),
    ("compliance", re.compile(r"compliance|on[- ]?contract|contract coverage", re.I)),
    ("leakage", re.compile(r"leakage|price variance|paid above|rate variance", re.I)),
    ("should_cost", re.compile(r"should[- ]?cost|should cost gap", re.I)),
    ("top_suppliers", re.compile(r"top suppliers|largest suppliers|supplier concentration", re.I)),
    ("direct_vs_indirect", re.compile(r"direct.*(indirect)|indirect.*(direct)|spend type", re.I)),
    ("savings", re.compile(r"realized savings|savings realized|\bsaved\b", re.I)),
    ("risk", re.compile(r"risk|high[- ]?risk supplier", re.I)),
]


SQL_TEMPLATES = {
    "total_spend": """
        select round(sum(total_spend), 2) as total_spend,
               round(sum(direct_spend), 2) as direct_spend,
               round(sum(indirect_spend), 2) as indirect_spend
        from gold.mart_monthly_executive
    """,
    "maverick": """
        select round(sum(maverick_spend), 2) as maverick_spend,
               round(100.0 * sum(maverick_spend) / nullif(sum(total_spend), 0), 2) as maverick_pct
        from gold.mart_monthly_executive
    """,
    "compliance": """
        select round(100.0 * sum(on_contract_spend) / nullif(sum(total_spend), 0), 2) as compliance_pct,
               round(sum(on_contract_spend), 2) as on_contract_spend,
               round(sum(off_contract_spend), 2) as off_contract_spend
        from gold.mart_monthly_executive
    """,
    "leakage": """
        select supplier_name, category_l3,
               round(rate_leakage, 2) as rate_leakage,
               round(spend, 2) as spend
        from analytics.leakage
        order by rate_leakage desc
        limit 10
    """,
    "should_cost": """
        select category_l3, spend_type,
               round(should_cost_gap, 2) as should_cost_gap,
               round(total_spend, 2) as spend
        from gold.mart_category_spend
        order by should_cost_gap desc
        limit 10
    """,
    "top_suppliers": """
        select supplier_name, supplier_tier,
               round(total_spend, 2) as total_spend,
               round(contract_compliance_rate * 100, 1) as compliance_pct
        from gold.mart_supplier_performance
        order by total_spend desc
        limit 10
    """,
    "direct_vs_indirect": """
        select round(sum(direct_spend), 2) as direct_spend,
               round(sum(indirect_spend), 2) as indirect_spend,
               round(100.0 * sum(direct_spend) / nullif(sum(total_spend), 0), 1) as direct_pct
        from gold.mart_monthly_executive
    """,
    "savings": """
        select round(sum(savings_realized), 2) as savings_realized,
               round(sum(rate_leakage), 2) as rate_leakage_offset
        from gold.mart_monthly_executive
    """,
    "risk": """
        select supplier_name, risk_tier,
               round(supplier_risk_score, 3) as risk_score,
               round(total_spend, 2) as total_spend
        from ml.supplier_risk
        where risk_tier = 'High'
        order by supplier_risk_score desc
        limit 10
    """,
    "opportunity": """
        select opportunity_type,
               round(opportunity_usd, 2) as opportunity_usd,
               playbook
        from analytics.opportunity
        order by opportunity_usd desc
    """,
}


def load_semantic_layer(path: Path | None = None) -> dict:
    p = path or (CONFIGS / "semantic_layer.yaml")
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_intent(question: str) -> str:
    for name, pattern in INTENT_PATTERNS:
        if pattern.search(question):
            return name
    return "total_spend"


def ask(question: str, db_path: Path | None = None) -> QueryResult:
    intent = resolve_intent(question)
    sql = SQL_TEMPLATES[intent].strip()
    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db), read_only=True)
    df = con.execute(sql).df()
    con.close()
    rows = df.to_dict(orient="records")
    answer = _narrate(intent, rows)
    return QueryResult(question=question, intent=intent, sql=sql, answer_text=answer, rows=rows)


def _narrate(intent: str, rows: list[dict]) -> str:
    if not rows:
        return "No rows returned for this question."
    r0 = rows[0]
    if intent == "total_spend":
        return (
            f"Enterprise invoice spend is ${r0['total_spend']:,.0f} "
            f"(Direct ${r0['direct_spend']:,.0f} / Indirect ${r0['indirect_spend']:,.0f})."
        )
    if intent == "maverick":
        return f"Maverick spend is ${r0['maverick_spend']:,.0f} ({r0['maverick_pct']}% of total)."
    if intent == "compliance":
        return (
            f"Contract compliance is {r0['compliance_pct']}% "
            f"(${r0['on_contract_spend']:,.0f} on-contract vs ${r0['off_contract_spend']:,.0f} off)."
        )
    if intent == "opportunity":
        parts = [f"{r['opportunity_type']}: ${r['opportunity_usd']:,.0f}" for r in rows]
        return "Savings opportunity stack - " + "; ".join(parts) + "."
    if intent in {"leakage", "should_cost", "top_suppliers", "risk"}:
        top = rows[0]
        label = top.get("supplier_name") or top.get("category_l3")
        return f"Top result: {label}. Returning {len(rows)} ranked rows for drill-down."
    if intent == "direct_vs_indirect":
        return (
            f"Direct ${r0['direct_spend']:,.0f} ({r0['direct_pct']}%) vs "
            f"Indirect ${r0['indirect_spend']:,.0f}."
        )
    if intent == "savings":
        return (
            f"Realized savings ${r0['savings_realized']:,.0f}; "
            f"rate leakage headwind ${r0['rate_leakage_offset']:,.0f}."
        )
    return str(r0)


DEMO_QUESTIONS = [
    "What is our total spend?",
    "Where is rate leakage highest?",
    "Show maverick spend",
    "What is contract compliance?",
    "Which suppliers are high risk?",
    "Where are the biggest savings opportunities?",
]


def demo() -> None:
    load_semantic_layer()  # validate YAML present
    print("ProcureIQ semantic QA demo\n" + "-" * 40)
    for q in DEMO_QUESTIONS:
        result = ask(q)
        print(f"Q: {q}")
        print(f"Intent: {result.intent}")
        print(f"A: {result.answer_text}\n")


if __name__ == "__main__":
    demo()
