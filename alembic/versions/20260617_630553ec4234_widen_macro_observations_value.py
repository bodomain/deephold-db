"""widen_macro_observations_value

Revision ID: 630553ec4234
Revises: 0001_initial
Create Date: 2026-06-17 12:38:10.725032

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '630553ec4234'
down_revision: str | Sequence[str] | None = '0001_initial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('macro_observations', 'value',
               existing_type=sa.Numeric(18, 6),
               type_=sa.Numeric(24, 6),
               existing_nullable=True)
    op.alter_column('prices_daily', 'volume',
               existing_type=sa.BIGINT(),
               nullable=True,
               existing_server_default=None)


def downgrade() -> None:
    op.alter_column('prices_daily', 'volume',
               existing_type=sa.BIGINT(),
               nullable=False)
    op.alter_column('macro_observations', 'value',
               existing_type=sa.Numeric(24, 6),
               type_=sa.Numeric(18, 6),
               existing_nullable=True)