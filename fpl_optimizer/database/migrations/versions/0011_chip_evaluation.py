"""Add chip evaluation runs.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Phase 11 chip-run table."""

    Base.metadata.tables["chip_run"].create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Remove saved chip opportunity evaluations."""

    Base.metadata.tables["chip_run"].drop(bind=op.get_bind(), checkfirst=True)

