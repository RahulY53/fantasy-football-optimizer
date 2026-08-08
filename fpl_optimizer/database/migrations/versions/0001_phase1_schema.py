"""Create the Phase 1 FPL data schema.

Revision ID: 0001
Revises: None
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all Phase 1 tables from the versioned metadata."""

    bind = op.get_bind()
    for table_name in (
        "data_snapshot",
        "gameweek",
        "team",
        "player",
        "player_snapshot",
        "fixture",
    ):
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Drop all Phase 1 tables when explicitly rolling back this revision."""

    bind = op.get_bind()
    for table_name in (
        "fixture",
        "player_snapshot",
        "player",
        "team",
        "gameweek",
        "data_snapshot",
    ):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
