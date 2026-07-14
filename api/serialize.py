"""Shared serialization helpers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def jsonable_rows(rows) -> list[dict[str, Any]]:
    return [jsonable_row(dict(r)) for r in rows]
