"""Preserve historical player availability observations.

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create append-only availability snapshots for change detection."""

    op.create_table(
        "player_availability_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("player.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "data_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("data_snapshot.id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("news", sa.Text(), nullable=False, server_default=""),
        sa.Column("chance_next_round", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "player_id", "data_snapshot_id", name="uq_player_availability_data_snapshot"
        ),
    )
    op.create_index(
        "ix_player_availability_snapshot_player_id",
        "player_availability_snapshot",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        "ix_player_availability_snapshot_observed_at",
        "player_availability_snapshot",
        ["observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_player_availability_player_observed",
        "player_availability_snapshot",
        ["player_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove historical availability observations."""

    op.drop_index(
        "ix_player_availability_player_observed",
        table_name="player_availability_snapshot",
    )
    op.drop_index(
        "ix_player_availability_snapshot_observed_at",
        table_name="player_availability_snapshot",
    )
    op.drop_index(
        "ix_player_availability_snapshot_player_id",
        table_name="player_availability_snapshot",
    )
    op.drop_table("player_availability_snapshot")
