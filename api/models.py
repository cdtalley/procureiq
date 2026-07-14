"""Star-schema ORM models for ProcureIQ."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class DimSupplier(Base):
    __tablename__ = "dim_supplier"

    supplier_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    primary_category: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)  # Low|Medium|High
    region: Mapped[str] = mapped_column(String(80), nullable=False)
    locality: Mapped[str] = mapped_column(String(20), default="domestic")  # domestic|import
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contracts: Mapped[list[DimContract]] = relationship(back_populates="supplier")
    spend_rows: Mapped[list[FactSpend]] = relationship(back_populates="supplier")


class DimCategory(Base):
    __tablename__ = "dim_category"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    parent_category: Mapped[str | None] = mapped_column(String(120))
    direct_or_indirect: Mapped[str] = mapped_column(String(20), nullable=False)  # Direct|Indirect

    spend_rows: Mapped[list[FactSpend]] = relationship(back_populates="category")


class DimContract(Base):
    __tablename__ = "dim_contract"

    contract_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("dim_supplier.supplier_id"), index=True)
    negotiated_rate: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    terms: Mapped[str] = mapped_column(Text, default="Net 45")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("dim_category.category_id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    supplier: Mapped[DimSupplier] = relationship(back_populates="contracts")
    spend_rows: Mapped[list[FactSpend]] = relationship(back_populates="contract")


class FactSpend(Base):
    __tablename__ = "fact_spend"
    __table_args__ = (UniqueConstraint("po_number", "line_number", name="uq_po_line"),)

    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("dim_supplier.supplier_id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("dim_category.category_id"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("dim_contract.contract_id"), index=True)
    po_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, default=1)
    invoice_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    negotiated_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    actual_rate: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    spend_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cost_center: Mapped[str] = mapped_column(String(40), nullable=False)
    is_maverick: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    supplier: Mapped[DimSupplier] = relationship(back_populates="spend_rows")
    category: Mapped[DimCategory] = relationship(back_populates="spend_rows")
    contract: Mapped[DimContract | None] = relationship(back_populates="spend_rows")


class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pass|fail|warn
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
