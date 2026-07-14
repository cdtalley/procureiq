"""Pydantic response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str
    service: str = "procureiq-api"


class MetricCard(BaseModel):
    total_spend: float
    yoy_change_pct: float | None
    contract_compliance_pct: float
    rate_leakage: float
    maverick_spend: float
    supplier_count: int
    transaction_count: int


class AgentAskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AgentAskOut(BaseModel):
    question: str
    answer: str
    sql: str
    intent: str
    rows: list[dict[str, Any]]
    mode: str  # llm | deterministic


class DQCheckOut(BaseModel):
    check_name: str
    status: str
    row_count: int
    detail: str
