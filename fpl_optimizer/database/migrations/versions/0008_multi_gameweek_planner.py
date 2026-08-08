"""Add multi-Gameweek planner runs.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Phase 8 planning-run table."""

    Base.metadata.tables["planner_run"].create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Remove saved multi-Gameweek planning runs."""

    Base.metadata.tables["planner_run"].drop(bind=op.get_bind(), checkfirst=True)

