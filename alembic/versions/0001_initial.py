"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-16
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("venue_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.Text, unique=True, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("timezone", sa.Text),
        sa.Column("country", sa.CHAR(2)),
    )

    op.create_table(
        "vendors",
        sa.Column("vendor_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.Text, unique=True),
        sa.Column("license", sa.Text),
        sa.Column("homepage", sa.Text),
    )

    op.create_table(
        "instruments",
        sa.Column("instrument_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("asset_class", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("currency", sa.CHAR(3)),
        sa.Column("primary_venue", sa.Integer, sa.ForeignKey("venues.venue_id")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "instrument_identifiers",
        sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.instrument_id"), nullable=False),
        sa.Column("scheme", sa.Text, primary_key=True, nullable=False),
        sa.Column("value", sa.Text, primary_key=True, nullable=False),
    )
    op.create_index(
        "ix_instrument_identifiers_instrument_id",
        "instrument_identifiers",
        ["instrument_id"],
    )

    op.create_table(
        "trading_calendars",
        sa.Column("venue_id", sa.Integer, sa.ForeignKey("venues.venue_id"), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("is_trading_day", sa.Boolean),
    )

    op.create_table(
        "prices_raw",
        sa.Column("vendor_id", sa.Integer, sa.ForeignKey("vendors.vendor_id"), primary_key=True),
        sa.Column("vendor_symbol", sa.Text, primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "prices_daily",
        sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.instrument_id"), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("open", sa.Numeric(18, 8)),
        sa.Column("high", sa.Numeric(18, 8)),
        sa.Column("low", sa.Numeric(18, 8)),
        sa.Column("close", sa.Numeric(18, 8)),
        sa.Column("adjusted_close", sa.Numeric(18, 8)),
        sa.Column("volume", sa.BigInteger),
        sa.Column("vendor_id", sa.Integer, sa.ForeignKey("vendors.vendor_id")),
    )
    op.create_index("ix_prices_daily_date", "prices_daily", ["date"])
    op.create_index("ix_prices_daily_instrument_id_date", "prices_daily", ["instrument_id", "date"])

    op.create_table(
        "corporate_actions",
        sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.instrument_id"), primary_key=True),
        sa.Column("ex_date", sa.Date, primary_key=True),
        sa.Column("action_type", sa.Text, primary_key=True),
        sa.Column("value", sa.Numeric(18, 8)),
    )

    op.create_table(
        "fx_rates_daily",
        sa.Column("ccy_from", sa.CHAR(3), primary_key=True),
        sa.Column("ccy_to", sa.CHAR(3), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("rate", sa.Numeric(18, 8)),
        sa.Column("vendor_id", sa.Integer, sa.ForeignKey("vendors.vendor_id")),
    )

    op.create_table(
        "bond_yields",
        sa.Column("instrument_id", sa.BigInteger, sa.ForeignKey("instruments.instrument_id"), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("yield", sa.Numeric(10, 6)),
        sa.Column("price", sa.Numeric(10, 6)),
        sa.Column("duration", sa.Numeric(10, 4)),
        sa.Column("rating", sa.Text),
    )

    op.create_table(
        "macro_series",
        sa.Column("series_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text),
        sa.Column("source", sa.Text),
        sa.Column("frequency", sa.Text),
        sa.Column("unit", sa.Text),
    )

    op.create_table(
        "macro_observations",
        sa.Column("series_id", sa.Text, sa.ForeignKey("macro_series.series_id"), primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("value", sa.Numeric(18, 6)),
    )

    op.create_table(
        "dq_runs",
        sa.Column("run_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("pipeline", sa.Text),
        sa.Column("status", sa.Text),
    )

    op.create_table(
        "dq_findings",
        sa.Column("run_id", sa.BigInteger, sa.ForeignKey("dq_runs.run_id"), primary_key=True),
        sa.Column("check_name", sa.Text, primary_key=True),
        sa.Column("severity", sa.Text),
        sa.Column("affected_rows", sa.Integer),
        sa.Column("details", postgresql.JSONB),
    )


def downgrade() -> None:
    op.drop_table("dq_findings")
    op.drop_table("dq_runs")
    op.drop_table("macro_observations")
    op.drop_table("macro_series")
    op.drop_table("bond_yields")
    op.drop_table("fx_rates_daily")
    op.drop_table("corporate_actions")
    op.drop_index("ix_prices_daily_instrument_id_date", table_name="prices_daily")
    op.drop_index("ix_prices_daily_date", table_name="prices_daily")
    op.drop_table("prices_daily")
    op.drop_table("prices_raw")
    op.drop_table("trading_calendars")
    op.drop_index("ix_instrument_identifiers_instrument_id", table_name="instrument_identifiers")
    op.drop_table("instrument_identifiers")
    op.drop_table("instruments")
    op.drop_table("vendors")
    op.drop_table("venues")
