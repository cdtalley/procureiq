"""Apply / refresh ProcureIQ semantic SQL views."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

VIEWS_PATH = Path(__file__).resolve().parent / "views.sql"


def apply_semantic_views(session: Session) -> None:
    sql = VIEWS_PATH.read_text(encoding="utf-8")
    # Split on statement boundaries while keeping view bodies intact
    for stmt in _split_sql(sql):
        session.execute(text(stmt))
    session.flush()


def _split_sql(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            chunk = "\n".join(buf).strip()
            if chunk:
                parts.append(chunk[:-1] if chunk.endswith(";") else chunk)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts
