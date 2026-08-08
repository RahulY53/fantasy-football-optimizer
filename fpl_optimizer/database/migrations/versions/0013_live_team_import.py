"""Add public FPL Team ID import metadata.

Revision ID: 0013
Revises: 0012
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend current-team records with public import provenance and roles."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    team_columns = {column["name"] for column in inspector.get_columns("user_team")}
    with op.batch_alter_table("user_team") as batch:
        for column in _team_columns():
            if column.name not in team_columns:
                batch.add_column(column)
    team_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("user_team")}
    if "ix_user_team_fpl_team_id" not in team_indexes:
        with op.batch_alter_table("user_team") as batch:
            batch.create_index("ix_user_team_fpl_team_id", ["fpl_team_id"], unique=True)
    player_columns = {column["name"] for column in sa.inspect(bind).get_columns("user_player")}
    with op.batch_alter_table("user_player") as batch:
        for column in _player_columns():
            if column.name not in player_columns:
                batch.add_column(column)


def _team_columns() -> tuple[sa.Column[Any], ...]:
    return (
        sa.Column("fpl_team_id", sa.Integer(), nullable=True),
        sa.Column("manager_name", sa.String(200), nullable=True),
        sa.Column("imported_team_name", sa.String(200), nullable=True),
        sa.Column("overall_rank", sa.Integer(), nullable=True),
        sa.Column("total_points", sa.Integer(), nullable=True),
        sa.Column("published_gameweek", sa.Integer(), nullable=True),
        sa.Column("squad_value_tenths", sa.Integer(), nullable=True),
        sa.Column("data_status", sa.String(40), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("history_json", sa.Text(), nullable=True),
        sa.Column("transfers_json", sa.Text(), nullable=True),
    )


def _player_columns() -> tuple[sa.Column[Any], ...]:
    return (
        sa.Column("imported_position", sa.Integer(), nullable=True),
        sa.Column("is_starting", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("bench_order", sa.Integer(), nullable=True),
        sa.Column("is_captain", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_vice_captain", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Remove public team import fields."""

    with op.batch_alter_table("user_player") as batch:
        for name in (
            "is_vice_captain",
            "is_captain",
            "bench_order",
            "is_starting",
            "imported_position",
        ):
            batch.drop_column(name)
    with op.batch_alter_table("user_team") as batch:
        batch.drop_index("ix_user_team_fpl_team_id")
        for name in (
            "transfers_json",
            "history_json",
            "imported_at",
            "data_status",
            "squad_value_tenths",
            "published_gameweek",
            "total_points",
            "overall_rank",
            "imported_team_name",
            "manager_name",
            "fpl_team_id",
        ):
            batch.drop_column(name)
