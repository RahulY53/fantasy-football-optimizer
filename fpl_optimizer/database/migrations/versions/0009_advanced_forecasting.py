"""Add advanced fixture and goalscorer markets.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from fpl_optimizer.database import models  # noqa: F401
from fpl_optimizer.database.base import Base

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create player odds and extend market forecast outputs."""

    Base.metadata.tables["goalscorer_odds_snapshot"].create(
        bind=op.get_bind(), checkfirst=True
    )
    bind = op.get_bind()
    market_columns = {column["name"] for column in sa.inspect(bind).get_columns("market_forecast")}
    with op.batch_alter_table("market_forecast") as batch:
        if "btts_yes" not in market_columns:
            batch.add_column(sa.Column("btts_yes", sa.Float(), nullable=True))
        if "home_over_1_5" not in market_columns:
            batch.add_column(sa.Column("home_over_1_5", sa.Float(), nullable=True))
        if "away_over_1_5" not in market_columns:
            batch.add_column(sa.Column("away_over_1_5", sa.Float(), nullable=True))
        if "advanced_market_count" not in market_columns:
            batch.add_column(
                sa.Column(
                    "advanced_market_count",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
    player_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("player_market_forecast")
    }
    if "goalscorer_probability" not in player_columns:
        with op.batch_alter_table("player_market_forecast") as batch:
            batch.add_column(sa.Column("goalscorer_probability", sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove advanced market fields and player-linked odds."""

    with op.batch_alter_table("player_market_forecast") as batch:
        batch.drop_column("goalscorer_probability")
    with op.batch_alter_table("market_forecast") as batch:
        batch.drop_column("advanced_market_count")
        batch.drop_column("away_over_1_5")
        batch.drop_column("home_over_1_5")
        batch.drop_column("btts_yes")
    Base.metadata.tables["goalscorer_odds_snapshot"].drop(
        bind=op.get_bind(), checkfirst=True
    )
