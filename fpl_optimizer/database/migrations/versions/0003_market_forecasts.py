"""Add odds and market forecasts.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Phase 3 odds and market forecast tables."""

    bind = op.get_bind()
    for table_name in ("odds_snapshot", "market_forecast", "player_market_forecast"):
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Remove Phase 3 tables in dependency-safe order."""

    bind = op.get_bind()
    for table_name in ("player_market_forecast", "market_forecast", "odds_snapshot"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
