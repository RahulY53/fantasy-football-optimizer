"""Add Monte Carlo simulation runs.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the Phase 10 simulation-run table."""

    Base.metadata.tables["simulation_run"].create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Remove saved Monte Carlo simulation runs."""

    Base.metadata.tables["simulation_run"].drop(bind=op.get_bind(), checkfirst=True)

