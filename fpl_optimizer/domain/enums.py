"""Shared domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class Position(StrEnum):
    """Official FPL squad positions."""

    GOALKEEPER = "GK"
    DEFENDER = "DEF"
    MIDFIELDER = "MID"
    FORWARD = "FWD"


class FixtureStatus(StrEnum):
    """Normalized fixture lifecycle state."""

    SCHEDULED = "scheduled"
    STARTED = "started"
    FINISHED = "finished"


class OddsMarket(StrEnum):
    """Supported fixture and player betting markets."""

    MATCH_RESULT = "1x2"
    TOTAL_GOALS_2_5 = "over_under_2_5"
    BTTS = "btts"
    HOME_TOTAL_1_5 = "home_total_1_5"
    AWAY_TOTAL_1_5 = "away_total_1_5"
    ANYTIME_GOALSCORER = "anytime_goalscorer"


class OddsSelection(StrEnum):
    """Selections supported by the MVP odds markets."""

    HOME = "home"
    DRAW = "draw"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"
    YES = "yes"
    NO = "no"
    SCORE = "score"


class OddsSnapshotKind(StrEnum):
    """Position of an odds observation in its market lifecycle."""

    OPENING = "opening"
    CURRENT = "current"
    CLOSING = "closing"
    PRE_DEADLINE = "pre_deadline"
