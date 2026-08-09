"""Add persistent player watchlist membership.

Revision ID: 0016
Revises: 0015
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the canonical player watchlist table."""

    op.create_table(
        "player_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id",
            sa.Integer(),
            sa.ForeignKey("player.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("player_id", name="uq_player_watchlist_player"),
    )
    op.create_index(
        "ix_player_watchlist_player_id", "player_watchlist", ["player_id"], unique=True
    )
    op.create_index(
        "ix_player_watchlist_created_at", "player_watchlist", ["created_at"], unique=False
    )
    op.create_index(
        "ix_player_watchlist_updated_at", "player_watchlist", ["updated_at"], unique=False
    )


def downgrade() -> None:
    """Remove persistent watchlist membership."""

    op.drop_index("ix_player_watchlist_updated_at", table_name="player_watchlist")
    op.drop_index("ix_player_watchlist_created_at", table_name="player_watchlist")
    op.drop_index("ix_player_watchlist_player_id", table_name="player_watchlist")
    op.drop_table("player_watchlist")
