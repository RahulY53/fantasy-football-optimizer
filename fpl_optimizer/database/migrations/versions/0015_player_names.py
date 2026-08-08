"""Add canonical full and display player names.

Revision ID: 0015
Revises: 0014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add, backfill, and index recognizable player names."""

    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("player")}
    with op.batch_alter_table("player") as batch:
        if "full_name" not in columns:
            batch.add_column(
                sa.Column("full_name", sa.String(220), nullable=False, server_default="")
            )
        if "display_name" not in columns:
            batch.add_column(
                sa.Column("display_name", sa.String(220), nullable=False, server_default="")
            )

    op.execute(
        sa.text(
            """
            UPDATE player
            SET full_name = CASE
                    WHEN trim(coalesce(first_name, '') || ' ' || coalesce(second_name, '')) = ''
                    THEN web_name
                    ELSE trim(coalesce(first_name, '') || ' ' || coalesce(second_name, ''))
                END,
                display_name = CASE
                    WHEN trim(coalesce(first_name, '') || ' ' || coalesce(second_name, '')) = ''
                    THEN web_name
                    ELSE trim(coalesce(first_name, '') || ' ' || coalesce(second_name, ''))
                END
            """
        )
    )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("player")}
    with op.batch_alter_table("player") as batch:
        if "ix_player_full_name" not in indexes:
            batch.create_index("ix_player_full_name", ["full_name"], unique=False)
        if "ix_player_display_name" not in indexes:
            batch.create_index("ix_player_display_name", ["display_name"], unique=False)


def downgrade() -> None:
    """Remove derived player-name columns."""

    with op.batch_alter_table("player") as batch:
        batch.drop_index("ix_player_display_name")
        batch.drop_index("ix_player_full_name")
        batch.drop_column("display_name")
        batch.drop_column("full_name")
