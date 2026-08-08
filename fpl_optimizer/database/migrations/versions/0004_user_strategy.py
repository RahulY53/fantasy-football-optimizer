"""Add saved user strategies.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Phase 4 strategy tables."""

    bind = op.get_bind()
    for table_name in ("strategy", "strategy_weight"):
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Remove Phase 4 tables in dependency-safe order."""

    bind = op.get_bind()
    for table_name in ("strategy_weight", "strategy"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
