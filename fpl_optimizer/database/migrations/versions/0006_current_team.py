"""Add current team and lineup runs.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Phase 6 current-team and lineup tables."""

    bind = op.get_bind()
    for table_name in ("user_team", "user_player", "lineup_run"):
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Remove Phase 6 tables in dependency-safe order."""

    bind = op.get_bind()
    for table_name in ("lineup_run", "user_player", "user_team"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
