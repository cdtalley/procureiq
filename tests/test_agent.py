from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from agent.graph import ask, resolve_intent
from api.db import Base
from api.models import DimCategory, DimContract, DimSupplier, FactSpend
from semantic.apply_views import apply_semantic_views


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    # Skip full PG views on SQLite — unit-test intent router only when no PG
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = TestingSession()
    yield s
    s.close()


def test_intent_leakage():
    assert resolve_intent("Which suppliers had the biggest price variance?") == "leakage"


def test_intent_maverick():
    assert resolve_intent("Show maverick spend outside contracts") == "maverick"


def test_intent_pvm():
    assert resolve_intent("Explain price volume mix for last month") == "pvm"


def test_agent_blocks_base_tables():
    from agent.graph import _assert_semantic_only
    import pytest

    with pytest.raises(ValueError):
        _assert_semantic_only("select * from fact_spend")
