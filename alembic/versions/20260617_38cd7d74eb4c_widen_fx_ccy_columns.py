"""widen_fx_ccy_columns

Revision ID: 38cd7d74eb4c
Revises: 630553ec4234
Create Date: 2026-06-17 11:15:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '38cd7d74eb4c'
down_revision: str | Sequence[str] | None = '630553ec4234'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('fx_rates_daily', 'ccy_from',
               existing_type=sa.String(3),
               type_=sa.String(7),
               existing_nullable=False)
    op.alter_column('fx_rates_daily', 'ccy_to',
               existing_type=sa.String(3),
               type_=sa.String(7),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('fx_rates_daily', 'ccy_to',
               existing_type=sa.String(7),
               type_=sa.String(3),
               existing_nullable=False)
    op.alter_column('fx_rates_daily', 'ccy_from',
               existing_type=sa.String(7),
               type_=sa.String(3),
               existing_nullable=False)