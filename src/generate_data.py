"""
Synthetic multi-system procurement landscape.

Emulates SAP POs, Oracle AP invoices, Coupa contracts, MDM suppliers,
category taxonomy, GL actuals, and engineering should-cost models -
with intentional leakage, maverick spend, and data-quality issues
so analytics products have something real to surface.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import DATA_RAW, ensure_dirs

RNG = np.random.default_rng(42)

DIRECT_CATEGORIES = [
    ("Direct", "Raw Materials", "Steel & Alloys", "RM-STEEL"),
    ("Direct", "Raw Materials", "Polymers & Resins", "RM-POLY"),
    ("Direct", "Components", "Electronics PCB", "CMP-PCB"),
    ("Direct", "Components", "Fasteners", "CMP-FAST"),
    ("Direct", "Packaging", "Corrugated", "PKG-CORR"),
    ("Direct", "Packaging", "Labels & Films", "PKG-LAB"),
]

INDIRECT_CATEGORIES = [
    ("Indirect", "Facilities", "MRO Supplies", "FAC-MRO"),
    ("Indirect", "Facilities", "HVAC Services", "FAC-HVAC"),
    ("Indirect", "IT", "Software Licenses", "IT-SaaS"),
    ("Indirect", "IT", "Hardware & Peripherals", "IT-HW"),
    ("Indirect", "Professional Services", "Consulting", "PS-CONS"),
    ("Indirect", "Professional Services", "Temp Labor", "PS-TEMP"),
    ("Indirect", "Logistics", "Parcel & Freight", "LOG-FRT"),
    ("Indirect", "Travel", "Corporate Travel", "TRV-AIR"),
]

SUPPLIER_NAMES = [
    "Apex Industrial Metals", "Northline Polymers", "Vertex Circuits",
    "Precision Fasteners Co", "BoxCraft Packaging", "ClearLabel Films",
    "PlantCare MRO", "ClimateWorks HVAC", "CloudStack Software",
    "ByteEdge Hardware", "Meridian Consulting", "FlexStaff Solutions",
    "Harborline Freight", "Skyward Travel Desk", "Summit Alloys",
    "Riverton Resins", "Orbit Electronics", "Titan Anchors",
    "GreenWrap Packaging", "FacilityFirst Supply", "NovaSoft Platforms",
    "PrimeTemps Inc", "TransAxis Logistics", "AeroLane Travel",
    "Atlas Steelworks", "Delta Components", "Echo Packaging",
    "Forge Industrial", "GlowTech Systems", "Helix Services",
]

COUNTRIES = ["US", "US", "US", "MX", "CA", "CN", "DE", "IN", "VN", "US"]
BUSINESS_UNITS = ["Manufacturing", "Corporate", "Aftermarket", "R&D"]
COST_CENTERS = [
    ("CC-100", "Plant Ops - Midwest", "Manufacturing"),
    ("CC-110", "Plant Ops - Southeast", "Manufacturing"),
    ("CC-200", "Corporate Procurement", "Corporate"),
    ("CC-210", "IT Shared Services", "Corporate"),
    ("CC-300", "Aftermarket Parts", "Aftermarket"),
    ("CC-400", "Product Engineering", "R&D"),
]


def _categories() -> pd.DataFrame:
    rows = []
    for i, (l1, l2, l3, code) in enumerate(DIRECT_CATEGORIES + INDIRECT_CATEGORIES, start=1):
        rows.append(
            {
                "category_id": f"CAT-{i:03d}",
                "category_code": code,
                "category_l1": l1,
                "category_l2": l2,
                "category_l3": l3,
                "unspsc_stub": f"{10000000 + i * 111}",
                "preferred_currency": "USD",
            }
        )
    return pd.DataFrame(rows)


def _suppliers(categories: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i, name in enumerate(SUPPLIER_NAMES, start=1):
        cat = categories.iloc[i % len(categories)]
        tier = RNG.choice(["Strategic", "Preferred", "Approved", "Tactical"], p=[0.15, 0.35, 0.35, 0.15])
        risk = float(np.clip(RNG.normal(0.35 if tier == "Strategic" else 0.5, 0.15), 0.05, 0.95))
        rows.append(
            {
                "supplier_id": f"SUP-{i:04d}",
                "supplier_name": name,
                "supplier_name_alias": name.upper().replace(" ", "")[:18] if RNG.random() < 0.2 else None,
                "country": RNG.choice(COUNTRIES),
                "tier": tier,
                "primary_category_id": cat["category_id"],
                "payment_terms_days": int(RNG.choice([30, 45, 60, 90], p=[0.4, 0.3, 0.2, 0.1])),
                "diversity_flag": bool(RNG.random() < 0.18),
                "active_flag": bool(RNG.random() > 0.05),
                "risk_score_seed": round(risk, 3),
                "on_time_delivery_hist": round(float(np.clip(RNG.normal(0.92, 0.06), 0.6, 0.99)), 3),
                "quality_ppm_hist": int(max(0, RNG.normal(250, 200))),
            }
        )
    # Intentional MDM duplicate / dirty record for governance demo
    rows.append(
        {
            "supplier_id": "SUP-0099",
            "supplier_name": "Apex Industrial Metals LLC",
            "supplier_name_alias": "APEXINDUSTRIAL",
            "country": "US",
            "tier": "Strategic",
            "primary_category_id": categories.iloc[0]["category_id"],
            "payment_terms_days": 45,
            "diversity_flag": False,
            "active_flag": True,
            "risk_score_seed": 0.28,
            "on_time_delivery_hist": 0.94,
            "quality_ppm_hist": 120,
        }
    )
    return pd.DataFrame(rows)


def _contracts(suppliers: pd.DataFrame, categories: pd.DataFrame, start: date) -> pd.DataFrame:
    rows = []
    active_suppliers = suppliers[suppliers["active_flag"]].copy()
    for i, (_, sup) in enumerate(active_suppliers.iterrows(), start=1):
        if RNG.random() < 0.25:
            continue
        cat_id = sup["primary_category_id"]
        base_price = float(RNG.uniform(8, 420))
        start_dt = start + timedelta(days=int(RNG.integers(-120, 60)))
        end_dt = start_dt + timedelta(days=int(RNG.choice([365, 730, 1095])))
        rows.append(
            {
                "contract_id": f"CTR-{i:04d}",
                "supplier_id": sup["supplier_id"],
                "category_id": cat_id,
                "contract_name": f"{sup['supplier_name'][:20]} MSA",
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "status": "Active" if end_dt >= start else "Expired",
                "unit_price": round(base_price, 2),
                "currency": "USD",
                "volume_commitment": int(RNG.integers(500, 50000)),
                "rebate_pct": round(float(RNG.choice([0.0, 0.01, 0.02, 0.03])), 3),
                "escalation_pct": round(float(RNG.choice([0.0, 0.02, 0.03])), 3),
            }
        )
    return pd.DataFrame(rows)


def _should_cost(categories: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, cat in categories.iterrows():
        material = float(RNG.uniform(5, 280))
        labor = float(RNG.uniform(1, 60))
        overhead = float(RNG.uniform(0.5, 40))
        freight = float(RNG.uniform(0.2, 18))
        quality = float(RNG.uniform(0.1, 12))
        rows.append(
            {
                "category_id": cat["category_id"],
                "material_cost": round(material, 2),
                "labor_cost": round(labor, 2),
                "overhead_cost": round(overhead, 2),
                "freight_cost": round(freight, 2),
                "quality_cost": round(quality, 2),
                "should_cost_unit": round(material + labor + overhead + freight + quality, 2),
                "model_version": "2025.Q4",
                "confidence": round(float(RNG.uniform(0.65, 0.95)), 2),
            }
        )
    return pd.DataFrame(rows)


def _transactions(
    suppliers: pd.DataFrame,
    categories: pd.DataFrame,
    contracts: pd.DataFrame,
    should_cost: pd.DataFrame,
    n_months: int = 24,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start = date.today().replace(day=1) - timedelta(days=30 * n_months)
    po_rows, inv_rows, gl_rows = [], [], []
    contract_by_sup = contracts.groupby("supplier_id")
    sc_map = should_cost.set_index("category_id")["should_cost_unit"].to_dict()
    cc_ids = [c[0] for c in COST_CENTERS]

    po_seq, inv_seq = 1, 1
    for m in range(n_months):
        period_start = (start + timedelta(days=30 * m)).replace(day=1)
        n_pos = int(RNG.integers(80, 140))
        for _ in range(n_pos):
            sup = suppliers.sample(1, random_state=int(RNG.integers(0, 1e9))).iloc[0]
            if not bool(sup["active_flag"]) and RNG.random() < 0.7:
                continue
            cat = categories[categories["category_id"] == sup["primary_category_id"]].iloc[0]
            if RNG.random() < 0.15:
                cat = categories.sample(1, random_state=int(RNG.integers(0, 1e9))).iloc[0]

            on_contract = True
            contracted_price = None
            contract_id = None
            if sup["supplier_id"] in contract_by_sup.groups:
                cands = contract_by_sup.get_group(sup["supplier_id"])
                cands = cands[cands["category_id"] == cat["category_id"]]
                if len(cands) and RNG.random() > 0.18:
                    ctr = cands.sample(1, random_state=int(RNG.integers(0, 1e9))).iloc[0]
                    contract_id = ctr["contract_id"]
                    contracted_price = float(ctr["unit_price"])
                else:
                    on_contract = False
            else:
                on_contract = False

            if contracted_price is None:
                contracted_price = float(sc_map.get(cat["category_id"], 50) * RNG.uniform(0.9, 1.15))

            # Leakage / premium / discount behaviors
            price_factor = 1.0
            if on_contract:
                price_factor = float(RNG.choice([1.0, 1.0, 1.02, 1.05, 1.12, 0.98], p=[0.45, 0.2, 0.15, 0.1, 0.05, 0.05]))
            else:
                price_factor = float(RNG.uniform(1.05, 1.35))

            # Occasional anomaly spike
            if RNG.random() < 0.02:
                price_factor *= float(RNG.uniform(1.5, 2.8))

            actual_unit_price = round(contracted_price * price_factor, 2)
            qty = int(RNG.integers(5, 800) if cat["category_l1"] == "Direct" else RNG.integers(1, 120))
            po_date = period_start + timedelta(days=int(RNG.integers(0, 27)))
            po_id = f"PO-{po_seq:06d}"
            po_seq += 1
            line_amt = round(qty * actual_unit_price, 2)
            baseline_price = round(contracted_price * 1.08, 2)
            savings = round(max(0, (baseline_price - actual_unit_price) * qty), 2)
            sc_unit = float(sc_map.get(cat["category_id"], actual_unit_price * 0.9))
            freight = round(line_amt * float(RNG.uniform(0.01, 0.06)), 2)
            quality_cost = round(line_amt * float(RNG.uniform(0.0, 0.03)), 2)
            payment_cost = round(line_amt * (sup["payment_terms_days"] / 365) * 0.05, 2)
            tco = round(line_amt + freight + quality_cost + payment_cost, 2)
            cc = RNG.choice(cc_ids)
            bu = dict(zip([c[0] for c in COST_CENTERS], [c[2] for c in COST_CENTERS]))[cc]

            po_rows.append(
                {
                    "po_id": po_id,
                    "po_line": 1,
                    "po_date": po_date.isoformat(),
                    "supplier_id": sup["supplier_id"],
                    "category_id": cat["category_id"],
                    "contract_id": contract_id,
                    "cost_center_id": cc,
                    "business_unit": bu,
                    "qty": qty,
                    "uom": "EA",
                    "unit_price": actual_unit_price,
                    "po_amount": line_amt,
                    "currency": "USD",
                    "buyer_id": f"BUY-{int(RNG.integers(1, 12)):02d}",
                    "status": RNG.choice(["Open", "Received", "Closed"], p=[0.1, 0.2, 0.7]),
                }
            )

            # Invoice (most POs get invoiced; some maverick invoices without PO)
            if RNG.random() < 0.92:
                inv_date = po_date + timedelta(days=int(RNG.integers(5, 45)))
                # invoice price variance vs PO
                inv_factor = float(RNG.choice([1.0, 1.0, 1.01, 1.03, 0.99], p=[0.6, 0.2, 0.1, 0.05, 0.05]))
                inv_price = round(actual_unit_price * inv_factor, 2)
                inv_amt = round(qty * inv_price, 2)
                inv_id = f"INV-{inv_seq:06d}"
                inv_seq += 1
                inv_rows.append(
                    {
                        "invoice_id": inv_id,
                        "invoice_line": 1,
                        "invoice_date": inv_date.isoformat(),
                        "po_id": po_id,
                        "supplier_id": sup["supplier_id"],
                        "category_id": cat["category_id"],
                        "contract_id": contract_id,
                        "cost_center_id": cc,
                        "business_unit": bu,
                        "qty": qty,
                        "unit_price": inv_price,
                        "invoice_amount": inv_amt,
                        "currency": "USD",
                        "payment_status": RNG.choice(["Paid", "Open", "Disputed"], p=[0.85, 0.12, 0.03]),
                        "maverick_flag": False,
                        "contracted_unit_price": round(contracted_price, 2),
                        "baseline_unit_price": baseline_price,
                        "should_cost_unit": round(sc_unit, 2),
                        "savings_realized": savings,
                        "freight_cost": freight,
                        "quality_cost": quality_cost,
                        "payment_terms_cost": payment_cost,
                        "tco_amount": tco,
                        "on_contract": on_contract and contract_id is not None,
                    }
                )

                gl_rows.append(
                    {
                        "gl_period": period_start.strftime("%Y-%m"),
                        "cost_center_id": cc,
                        "category_id": cat["category_id"],
                        "gl_account": "5100-Materials" if cat["category_l1"] == "Direct" else "6200-OpEx",
                        "actual_amount": inv_amt,
                        "budget_amount": round(inv_amt * float(RNG.uniform(0.92, 1.12)), 2),
                        "forecast_amount": round(inv_amt * float(RNG.uniform(0.95, 1.08)), 2),
                    }
                )

        # Pure maverick / non-PO invoices
        for _ in range(int(RNG.integers(3, 10))):
            sup = suppliers.sample(1, random_state=int(RNG.integers(0, 1e9))).iloc[0]
            cat = categories.sample(1, random_state=int(RNG.integers(0, 1e9))).iloc[0]
            qty = int(RNG.integers(1, 40))
            price = float(RNG.uniform(25, 900))
            inv_date = period_start + timedelta(days=int(RNG.integers(0, 27)))
            inv_amt = round(qty * price, 2)
            sc_unit = float(sc_map.get(cat["category_id"], price * 0.8))
            inv_id = f"INV-{inv_seq:06d}"
            inv_seq += 1
            cc = RNG.choice(cc_ids)
            bu = dict(zip([c[0] for c in COST_CENTERS], [c[2] for c in COST_CENTERS]))[cc]
            inv_rows.append(
                {
                    "invoice_id": inv_id,
                    "invoice_line": 1,
                    "invoice_date": inv_date.isoformat(),
                    "po_id": None,
                    "supplier_id": sup["supplier_id"],
                    "category_id": cat["category_id"],
                    "contract_id": None,
                    "cost_center_id": cc,
                    "business_unit": bu,
                    "qty": qty,
                    "unit_price": round(price, 2),
                    "invoice_amount": inv_amt,
                    "currency": "USD",
                    "payment_status": "Paid",
                    "maverick_flag": True,
                    "contracted_unit_price": round(price * 0.85, 2),
                    "baseline_unit_price": round(price * 0.95, 2),
                    "should_cost_unit": round(sc_unit, 2),
                    "savings_realized": 0.0,
                    "freight_cost": round(inv_amt * 0.04, 2),
                    "quality_cost": round(inv_amt * 0.02, 2),
                    "payment_terms_cost": round(inv_amt * 0.01, 2),
                    "tco_amount": round(inv_amt * 1.07, 2),
                    "on_contract": False,
                }
            )

    return pd.DataFrame(po_rows), pd.DataFrame(inv_rows), pd.DataFrame(gl_rows)


def _cost_centers() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"cost_center_id": a, "cost_center_name": b, "business_unit": c}
            for a, b, c in COST_CENTERS
        ]
    )


def generate(n_months: int = 24, out_dir: Path | None = None) -> dict[str, Path]:
    ensure_dirs()
    out = Path(out_dir) if out_dir else DATA_RAW
    out.mkdir(parents=True, exist_ok=True)

    categories = _categories()
    suppliers = _suppliers(categories)
    start = date.today().replace(day=1) - timedelta(days=30 * n_months)
    contracts = _contracts(suppliers, categories, start)
    should_cost = _should_cost(categories)
    pos, invoices, gl = _transactions(suppliers, categories, contracts, should_cost, n_months=n_months)
    cost_centers = _cost_centers()

    outputs = {
        "categories": out / "categories.csv",
        "suppliers": out / "suppliers.csv",
        "contracts": out / "contracts.csv",
        "should_cost": out / "should_cost.csv",
        "purchase_orders": out / "purchase_orders.csv",
        "invoices": out / "invoices.csv",
        "gl_actuals": out / "gl_actuals.csv",
        "cost_centers": out / "cost_centers.csv",
    }
    categories.to_csv(outputs["categories"], index=False)
    suppliers.to_csv(outputs["suppliers"], index=False)
    contracts.to_csv(outputs["contracts"], index=False)
    should_cost.to_csv(outputs["should_cost"], index=False)
    pos.to_csv(outputs["purchase_orders"], index=False)
    invoices.to_csv(outputs["invoices"], index=False)
    gl.to_csv(outputs["gl_actuals"], index=False)
    cost_centers.to_csv(outputs["cost_centers"], index=False)

    print(f"Generated synthetic procurement landscape -> {out}")
    print(f"  suppliers={len(suppliers):,}  contracts={len(contracts):,}  POs={len(pos):,}  invoices={len(invoices):,}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ProcureIQ synthetic source data")
    parser.add_argument("--months", type=int, default=24)
    args = parser.parse_args()
    generate(n_months=args.months)


if __name__ == "__main__":
    main()
