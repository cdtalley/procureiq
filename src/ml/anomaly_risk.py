"""Spend anomaly detection + supplier risk scoring for AI-ready procurement."""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src.paths import DATA_EXPORTS, WAREHOUSE_DB, ensure_dirs


def detect_spend_anomalies(db_path: Path | None = None, contamination: float = 0.03) -> pd.DataFrame:
    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db), read_only=True)
    df = con.execute(
        """
        select
            invoice_id,
            invoice_date,
            supplier_id,
            category_id,
            spend_type,
            category_l3,
            qty,
            actual_unit_price,
            invoice_amount,
            contracted_unit_price,
            should_cost_unit,
            price_variance,
            should_cost_gap,
            on_contract::int as on_contract_int,
            maverick_flag::int as maverick_int
        from gold.fact_spend
        """
    ).df()
    con.close()

    features = [
        "qty",
        "actual_unit_price",
        "invoice_amount",
        "price_variance",
        "should_cost_gap",
        "on_contract_int",
        "maverick_int",
    ]
    x = df[features].fillna(0).to_numpy()
    x_scaled = StandardScaler().fit_transform(x)
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    df["anomaly_label"] = model.fit_predict(x_scaled)
    df["anomaly_score"] = -model.score_samples(x_scaled)
    df["is_anomaly"] = df["anomaly_label"] == -1
    return df.sort_values("anomaly_score", ascending=False)


def score_supplier_risk(db_path: Path | None = None) -> pd.DataFrame:
    """
    Composite supplier risk score [0, 1]:
      - operational (OTD, quality)
      - commercial (leakage, maverick, compliance)
      - concentration (spend share)
    """
    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db), read_only=True)
    df = con.execute(
        """
        select
            sp.*,
            sp.total_spend / sum(sp.total_spend) over () as spend_share
        from gold.mart_supplier_performance sp
        """
    ).df()
    con.close()

    otd_risk = 1 - df["otd_rate"].fillna(0.9)
    quality_risk = np.clip(df["quality_ppm"].fillna(300) / 800, 0, 1)
    pos_leakage = df["rate_leakage"].fillna(0).clip(lower=0)
    leakage_risk = np.clip(pos_leakage / df["total_spend"].clip(lower=1) * 4, 0, 1)
    maverick_risk = np.clip(
        df["maverick_spend"].fillna(0) / df["total_spend"].clip(lower=1) * 2, 0, 1
    )
    compliance_risk = 1 - df["contract_compliance_rate"].fillna(0.5).clip(0, 1)
    concentration_risk = np.clip(df["spend_share"] / 0.10, 0, 1)

    df["risk_operational"] = 0.55 * otd_risk + 0.45 * quality_risk
    df["risk_commercial"] = 0.4 * leakage_risk + 0.35 * compliance_risk + 0.25 * maverick_risk
    df["risk_concentration"] = concentration_risk
    raw = (
        0.30 * df["risk_operational"]
        + 0.50 * df["risk_commercial"]
        + 0.20 * df["risk_concentration"]
    ).clip(0, 1)
    # Rank-normalize so portfolio always surfaces High / Medium / Low cohorts for action
    df["supplier_risk_score"] = raw.rank(pct=True)
    df["risk_tier"] = pd.qcut(
        df["supplier_risk_score"],
        q=[0, 0.5, 0.8, 1.0],
        labels=["Low", "Medium", "High"],
        duplicates="drop",
    )
    return df.sort_values("supplier_risk_score", ascending=False)


def run(db_path: Path | None = None) -> None:
    ensure_dirs()
    DATA_EXPORTS.mkdir(parents=True, exist_ok=True)
    anomalies = detect_spend_anomalies(db_path)
    risk = score_supplier_risk(db_path)

    anomalies_out = anomalies[anomalies["is_anomaly"]].head(500)
    anomalies_out.to_csv(DATA_EXPORTS / "spend_anomalies.csv", index=False)
    risk.to_csv(DATA_EXPORTS / "supplier_risk_scores.csv", index=False)

    db = Path(db_path) if db_path else WAREHOUSE_DB
    con = duckdb.connect(str(db))
    con.execute("create schema if not exists ml")
    con.execute("create or replace table ml.spend_anomalies as select * from anomalies")
    con.execute("create or replace table ml.supplier_risk as select * from risk")
    con.close()
    print(
        f"ML complete: {anomalies['is_anomaly'].sum()} anomalies flagged; "
        f"{(risk['risk_tier'] == 'High').sum()} high-risk suppliers"
    )


if __name__ == "__main__":
    run()
