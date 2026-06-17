"""Test that all 14 ORM models register on Base.metadata and emit DDL."""

from __future__ import annotations

from sqlalchemy import create_engine

from deephold_db.db import models  # noqa: F401
from deephold_db.db.base import Base


def test_all_tables_registered() -> None:
    expected = {
        "venues",
        "vendors",
        "instruments",
        "instrument_identifiers",
        "trading_calendars",
        "prices_raw",
        "prices_daily",
        "corporate_actions",
        "fx_rates_daily",
        "bond_yields",
        "macro_series",
        "macro_observations",
        "dq_runs",
        "dq_findings",
    }
    actual = set(Base.metadata.tables.keys())
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"missing tables: {missing}"
    assert not extra, f"unexpected tables: {extra}"


def test_metadata_emits_ddl() -> None:
    """DDL emission should not raise (catches column-type / FK issues)."""
    engine = create_engine("sqlite:///:memory:")
    ddl = []
    for table in Base.metadata.sorted_tables:
        ddl.append(str(table.compile(engine)))
    assert len(ddl) == 14
