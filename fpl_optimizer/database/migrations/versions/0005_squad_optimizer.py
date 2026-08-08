"""Add persisted squad optimization runs.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Phase 5 optimization run table."""

    Base.metadata.tables["optimization_run"].create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Remove saved optimization runs."""

    Base.metadata.tables["optimization_run"].drop(bind=op.get_bind(), checkfirst=True)
