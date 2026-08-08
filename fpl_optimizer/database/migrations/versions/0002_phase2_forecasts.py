"""Add versioned statistical forecasts.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Phase 2 model-version and player-forecast tables."""

    bind = op.get_bind()
    for table_name in ("model_version", "player_forecast"):
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Remove only the tables introduced in Phase 2."""

    bind = op.get_bind()
    Base.metadata.tables["player_forecast"].drop(bind=bind, checkfirst=True)
    Base.metadata.tables["model_version"].drop(bind=bind, checkfirst=True)
