"""Data quality gates for ProcureIQ ETL."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.models import DataQualityResult


CHECKS = [
    (
        "null_supplier_or_category",
        """
        select count(*) from fact_spend
        where supplier_id is null or category_id is null
        """,
        "fail_if_gt",
        0,
        "Fact rows missing supplier or category keys",
    ),
    (
        "negative_invoice_amounts",
        """
        select count(*) from fact_spend where invoice_amount < 0
        """,
        "warn_if_gt",
        0,
        "Negative invoice amounts require finance review",
    ),
    (
        "duplicate_po_lines",
        """
        select count(*) from (
          select po_number, line_number, count(*) c
          from fact_spend
          group by 1, 2
          having count(*) > 1
        ) d
        """,
        "fail_if_gt",
        0,
        "Duplicate PO line grain violations",
    ),
    (
        "actual_rate_null",
        """
        select count(*) from fact_spend where actual_rate is null
        """,
        "fail_if_gt",
        0,
        "Actual rate required for variance analytics",
    ),
    (
        "future_dated_spend",
        """
        select count(*) from fact_spend where spend_date > current_date + 30
        """,
        "warn_if_gt",
        0,
        "Spend dated more than 30 days in the future",
    ),
]


def run_data_quality(session: Session) -> list[DataQualityResult]:
    session.execute(text("delete from data_quality_results"))
    results: list[DataQualityResult] = []
    for name, sql, mode, threshold, detail in CHECKS:
        n = int(session.execute(text(sql)).scalar() or 0)
        if mode == "fail_if_gt":
            status = "pass" if n <= threshold else "fail"
        else:
            status = "pass" if n <= threshold else "warn"
        row = DataQualityResult(
            check_name=name,
            status=status,
            row_count=n,
            detail=f"{detail} (count={n})",
        )
        session.add(row)
        results.append(row)
    session.flush()
    return results
