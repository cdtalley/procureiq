"""Generate realistic synthetic procurement spend for ProcureIQ."""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import delete, text

from api.db import Base, SessionLocal, engine, wait_for_db
from api.logging_setup import configure_logging, get_logger
from api.models import DimCategory, DimContract, DimSupplier, FactSpend
from etl.dq import run_data_quality
from semantic.apply_views import apply_semantic_views

configure_logging()
log = get_logger("etl.seed")

CATEGORIES = [
    ("Raw Materials - Steel", "Raw Materials", "Direct"),
    ("Raw Materials - Polymers", "Raw Materials", "Direct"),
    ("MRO - Tools", "MRO", "Indirect"),
    ("MRO - Safety", "MRO", "Indirect"),
    ("IT Hardware", "IT", "Indirect"),
    ("IT Software & SaaS", "IT", "Indirect"),
    ("Professional Services", "Services", "Indirect"),
    ("Logistics & Freight", "Logistics", "Indirect"),
    ("Facilities & Utilities", "Facilities", "Indirect"),
    ("Packaging", "Raw Materials", "Direct"),
]

SUPPLIER_PREFIXES = [
    "Apex", "Northstar", "Summit", "Cascade", "Harbor", "Vertex", "Pinnacle",
    "Ironclad", "BlueRidge", "Meridian", "Atlas", "Cobalt", "Horizon", "Sterling",
    "Keystone", "Frontier", "Pacific", "Lakewood", "Granite", "Oakmont",
]
SUPPLIER_SUFFIXES = [
    "Industries", "Supply Co", "Materials", "Logistics", "Systems",
    "Partners", "Group", "Solutions", "Corp", "Vendors",
]
REGIONS = ["Midwest", "Southeast", "Northeast", "West", "Gulf Coast", "EMEA", "APAC"]
COST_CENTERS = ["CC-OPS-100", "CC-OPS-200", "CC-IT-310", "CC-FIN-400", "CC-MFG-110", "CC-LOG-220"]
RISK_TIERS = ["Low", "Low", "Medium", "Medium", "High"]


def _money(x: float) -> Decimal:
    return Decimal(str(round(x, 4)))


def wipe(session) -> None:
    session.execute(text("drop view if exists semantic.v_spend_cube cascade"))
    session.execute(text("drop view if exists semantic.v_price_variance cascade"))
    session.execute(text("drop view if exists semantic.v_tco_by_supplier cascade"))
    session.execute(text("drop view if exists semantic.v_pvm_monthly cascade"))
    session.execute(text("drop view if exists semantic.v_maverick_spend cascade"))
    session.execute(text("drop view if exists semantic.v_executive_monthly cascade"))
    session.execute(text("drop schema if exists semantic cascade"))
    session.execute(delete(FactSpend))
    session.execute(delete(DimContract))
    session.execute(delete(DimSupplier))
    session.execute(delete(DimCategory))
    session.commit()


def seed(
    n_suppliers: int = 50,
    n_contracts: int = 220,
    n_transactions: int = 5500,
    months: int = 18,
    seed: int = 42,
) -> None:
    rng = random.Random(seed)
    wait_for_db()
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        wipe(session)

        categories: list[DimCategory] = []
        for i, (name, parent, dio) in enumerate(CATEGORIES, start=1):
            cat = DimCategory(
                category_id=i,
                name=name,
                parent_category=parent,
                direct_or_indirect=dio,
            )
            session.add(cat)
            categories.append(cat)
        session.flush()

        suppliers: list[DimSupplier] = []
        used_names: set[str] = set()
        for sid in range(1, n_suppliers + 1):
            while True:
                name = f"{rng.choice(SUPPLIER_PREFIXES)} {rng.choice(SUPPLIER_SUFFIXES)}"
                if name not in used_names:
                    used_names.add(name)
                    break
            primary = rng.choice(categories)
            suppliers.append(
                DimSupplier(
                    supplier_id=sid,
                    name=name,
                    primary_category=primary.parent_category or primary.name,
                    risk_tier=rng.choice(RISK_TIERS),
                    region=rng.choice(REGIONS),
                    locality="import" if rng.random() < 0.25 else "domestic",
                )
            )
        session.add_all(suppliers)
        session.flush()

        end = date.today().replace(day=1) - timedelta(days=1)
        start = (end.replace(day=1) - relativedelta(months=months - 1))

        contracts: list[DimContract] = []
        for cid in range(1, n_contracts + 1):
            supplier = rng.choice(suppliers)
            cat = rng.choice(categories)
            c_start = start + timedelta(days=rng.randint(0, 120))
            c_end = c_start + timedelta(days=rng.randint(365, 900))
            base_rate = rng.uniform(8, 450)
            if "IT Software" in cat.name:
                base_rate = rng.uniform(20, 120)
            if "Professional" in cat.name:
                base_rate = rng.uniform(80, 350)
            if "Logistics" in cat.name:
                base_rate = rng.uniform(1.5, 25)
            contracts.append(
                DimContract(
                    contract_id=cid,
                    supplier_id=supplier.supplier_id,
                    negotiated_rate=_money(base_rate),
                    start_date=c_start,
                    end_date=c_end,
                    terms=rng.choice(["Net 30", "Net 45", "Net 60", "2/10 Net 30"]),
                    category_id=cat.category_id,
                    is_active=c_end >= end,
                )
            )
        session.add_all(contracts)
        session.flush()

        # Index contracts by supplier for assignment
        by_supplier: dict[int, list[DimContract]] = {}
        for c in contracts:
            by_supplier.setdefault(c.supplier_id, []).append(c)

        facts: list[FactSpend] = []
        span_days = (end - start).days
        po_counter = 100000

        for i in range(n_transactions):
            supplier = rng.choice(suppliers)
            cat = rng.choice(categories)
            spend_dt = start + timedelta(days=rng.randint(0, max(span_days, 1)))
            supplier_contracts = [
                c
                for c in by_supplier.get(supplier.supplier_id, [])
                if c.start_date <= spend_dt <= c.end_date
                and (c.category_id is None or c.category_id == cat.category_id or rng.random() < 0.4)
            ]

            is_maverick = rng.random() < 0.12 or not supplier_contracts
            contract = None if is_maverick else rng.choice(supplier_contracts)

            if contract:
                negotiated = float(contract.negotiated_rate)
            else:
                negotiated = rng.uniform(10, 300)

            # Deliberate leakage: ~18% of on-contract rows pay >5% above negotiated
            roll = rng.random()
            if contract and roll < 0.18:
                actual = negotiated * rng.uniform(1.06, 1.28)
            elif contract and roll < 0.30:
                actual = negotiated * rng.uniform(0.92, 0.99)  # slight under / savings
            else:
                actual = negotiated * rng.uniform(0.98, 1.03)

            qty = rng.choice([1, 2, 5, 10, 12, 20, 50, 100, 250])
            if "Professional" in cat.name:
                qty = rng.randint(8, 160)  # hours
            invoice = round(actual * qty, 2)

            po_counter += 1
            facts.append(
                FactSpend(
                    supplier_id=supplier.supplier_id,
                    category_id=cat.category_id,
                    contract_id=None if is_maverick else contract.contract_id,
                    po_number=f"PO-{po_counter}",
                    line_number=1,
                    invoice_amount=_money(invoice),
                    negotiated_rate=_money(negotiated) if contract else None,
                    actual_rate=_money(actual),
                    quantity=_money(qty),
                    spend_date=spend_dt,
                    cost_center=rng.choice(COST_CENTERS),
                    is_maverick=is_maverick,
                )
            )

            if len(facts) >= 500:
                session.add_all(facts)
                session.flush()
                facts.clear()

        if facts:
            session.add_all(facts)
        session.commit()

        # Inject a handful of DQ failures for the check step to surface
        # (negative amount + duplicate PO) then leave them for dq.py to flag
        bad = FactSpend(
            supplier_id=suppliers[0].supplier_id,
            category_id=categories[0].category_id,
            contract_id=None,
            po_number="PO-DQ-NEG",
            line_number=1,
            invoice_amount=_money(-125.0),
            negotiated_rate=None,
            actual_rate=_money(10.0),
            quantity=_money(1),
            spend_date=end,
            cost_center=COST_CENTERS[0],
            is_maverick=True,
        )
        session.add(bad)
        session.commit()

        apply_semantic_views(session)
        dq = run_data_quality(session)
        session.commit()

        n_fact = session.execute(text("select count(*) from fact_spend")).scalar()
        n_leak = session.execute(
            text(
                """
                select count(*) from semantic.v_price_variance
                where variance_flag
                """
            )
        ).scalar()
        log.info(
            "seed_complete",
            suppliers=n_suppliers,
            contracts=n_contracts,
            transactions=n_fact,
            leakage_rows=n_leak,
            dq_checks=len(dq),
        )
        print(
            f"ProcureIQ seed OK — suppliers={n_suppliers} contracts={n_contracts} "
            f"transactions={n_fact} leakage_flags={n_leak}"
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ProcureIQ synthetic spend")
    parser.add_argument("--suppliers", type=int, default=50)
    parser.add_argument("--contracts", type=int, default=220)
    parser.add_argument("--transactions", type=int, default=5500)
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    seed(
        n_suppliers=args.suppliers,
        n_contracts=args.contracts,
        n_transactions=args.transactions,
        months=args.months,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
