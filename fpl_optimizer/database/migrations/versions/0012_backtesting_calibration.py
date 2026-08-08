"""Add historical outcomes and forecast calibration runs.

Revision ID: 0012
Revises: 0011
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Phase 12 outcome and backtest-run tables."""

    bind = op.get_bind()
    Base.metadata.tables["player_gameweek_actual"].create(bind=bind, checkfirst=True)
    Base.metadata.tables["backtest_run"].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Remove historical calibration data."""

    bind = op.get_bind()
    Base.metadata.tables["backtest_run"].drop(bind=bind, checkfirst=True)
    Base.metadata.tables["player_gameweek_actual"].drop(bind=bind, checkfirst=True)
