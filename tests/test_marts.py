"""Smoke tests for warehouse marts after full build."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.paths import WAREHOUSE_DB


@pytest.fixture(scope="module")
def con():
    if not WAREHOUSE_DB.exists():
        pytest.skip("Warehouse not built — run python run_all.py first")
    c = duckdb.connect(str(WAREHOUSE_DB), read_only=True)
    yield c
    c.close()


def test_fact_spend_not_empty(con):
    n = con.execute("select count(*) from gold.fact_spend").fetchone()[0]
    assert n > 1000


def test_spend_cube_grain(con):
    n = con.execute("select count(*) from gold.spend_cube").fetchone()[0]
    assert n > 100


def test_compliance_between_0_and_1(con):
    row = con.execute(
        """
        select
            sum(on_contract_spend) / sum(total_spend) as c
        from gold.mart_monthly_executive
        """
    ).fetchone()[0]
    assert 0 < row < 1


def test_dq_rules_exist(con):
    n = con.execute("select count(*) from silver.data_quality_results").fetchone()[0]
    assert n >= 4


def test_ml_risk_scores(con):
    n = con.execute("select count(*) from ml.supplier_risk where supplier_risk_score between 0 and 1").fetchone()[0]
    assert n > 0


def test_opportunity_stack(con):
    types = {
        r[0]
        for r in con.execute("select opportunity_type from analytics.opportunity").fetchall()
    }
    assert "rate_leakage" in types
    assert "maverick_spend" in types
