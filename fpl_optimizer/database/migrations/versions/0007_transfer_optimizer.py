"""Add transfer evaluation runs.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Phase 7 transfer plan table."""

    Base.metadata.tables["transfer_plan"].create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Remove saved transfer evaluation runs."""

    Base.metadata.tables["transfer_plan"].drop(bind=op.get_bind(), checkfirst=True)
