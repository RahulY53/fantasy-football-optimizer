"""Add 2026/27 FPL scoring inputs and forecast components.

Revision ID: 0014
Revises: 0013
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store official defensive/event totals and defensive-contribution xPts."""

    bind = op.get_bind()
    _add_missing("player_snapshot", _snapshot_columns(), bind)
    _add_missing("player_forecast", _forecast_columns(), bind)
    _add_missing("player_market_forecast", _forecast_columns(), bind)


def _add_missing(table: str, columns: tuple[sa.Column[Any], ...], bind: Any) -> None:
    existing = {column["name"] for column in sa.inspect(bind).get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for column in columns:
            if column.name not in existing:
                batch.add_column(column)


def _snapshot_columns() -> tuple[sa.Column[Any], ...]:
    return tuple(
        sa.Column(name, sa.Integer(), nullable=False, server_default="0")
        for name in (
            "own_goals",
            "penalties_saved",
            "penalties_missed",
            "yellow_cards",
            "red_cards",
            "clearances_blocks_interceptions",
            "tackles",
            "recoveries",
            "defensive_contribution",
        )
    )


def _forecast_columns() -> tuple[sa.Column[Any], ...]:
    return (
        sa.Column(
            "defensive_contribution_xpts",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Remove the 2026/27 scoring fields."""

    for table in ("player_market_forecast", "player_forecast"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("defensive_contribution_xpts")
    with op.batch_alter_table("player_snapshot") as batch:
        for name in reversed(tuple(column.name for column in _snapshot_columns())):
            batch.drop_column(name)
