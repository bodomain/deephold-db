"""ORM models matching AGENTS.md schema (14 tables)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from finance_data.db.base import Base

# ---------------------------------------------------------------------------
# Stammdaten
# ---------------------------------------------------------------------------


class Venue(Base):
    __tablename__ = "venues"

    venue_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(CHAR(2))


class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(Text, unique=True)
    license: Mapped[str | None] = mapped_column(Text)
    homepage: Mapped[str | None] = mapped_column(Text)


class Instrument(Base):
    __tablename__ = "instruments"

    instrument_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    asset_class: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str | None] = mapped_column(CHAR(3))
    primary_venue: Mapped[int | None] = mapped_column(Integer, ForeignKey("venues.venue_id"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=func.true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InstrumentIdentifier(Base):
    __tablename__ = "instrument_identifiers"

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.instrument_id"), nullable=False
    )
    scheme: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)

    __table_args__ = (Index("ix_instrument_identifiers_instrument_id", "instrument_id"),)


class TradingCalendar(Base):
    __tablename__ = "trading_calendars"

    venue_id: Mapped[int] = mapped_column(Integer, ForeignKey("venues.venue_id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_trading_day: Mapped[bool | None] = mapped_column(Boolean)


# ---------------------------------------------------------------------------
# Preise
# ---------------------------------------------------------------------------


class PricesRaw(Base):
    __tablename__ = "prices_raw"

    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vendors.vendor_id"), primary_key=True
    )
    vendor_symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PricesDaily(Base):
    __tablename__ = "prices_daily"

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.instrument_id"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    vendor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("vendors.vendor_id"))

    __table_args__ = (
        Index("ix_prices_daily_date", "date"),
        Index("ix_prices_daily_instrument_id_date", "instrument_id", "date"),
    )


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.instrument_id"), primary_key=True
    )
    ex_date: Mapped[date] = mapped_column(Date, primary_key=True)
    action_type: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))


class FxRateDaily(Base):
    __tablename__ = "fx_rates_daily"

    ccy_from: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    ccy_to: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    vendor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("vendors.vendor_id"))


class BondYield(Base):
    __tablename__ = "bond_yields"

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.instrument_id"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    yield_: Mapped[Decimal | None] = mapped_column("yield", Numeric(10, 6))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    duration: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    rating: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Makro
# ---------------------------------------------------------------------------


class MacroSeries(Base):
    __tablename__ = "macro_series"

    series_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)


class MacroObservation(Base):
    __tablename__ = "macro_observations"

    series_id: Mapped[str] = mapped_column(
        Text, ForeignKey("macro_series.series_id"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))


# ---------------------------------------------------------------------------
# Datenqualität
# ---------------------------------------------------------------------------


class DqRun(Base):
    __tablename__ = "dq_runs"

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    pipeline: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)


class DqFinding(Base):
    __tablename__ = "dq_findings"

    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dq_runs.run_id"), primary_key=True
    )
    check_name: Mapped[str] = mapped_column(Text, primary_key=True)
    severity: Mapped[str | None] = mapped_column(Text)
    affected_rows: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSONB)


__all__ = [
    "Base",
    "BondYield",
    "CorporateAction",
    "DqFinding",
    "DqRun",
    "FxRateDaily",
    "Instrument",
    "InstrumentIdentifier",
    "MacroObservation",
    "MacroSeries",
    "PricesDaily",
    "PricesRaw",
    "TradingCalendar",
    "Vendor",
    "Venue",
]
