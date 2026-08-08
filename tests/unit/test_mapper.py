"""Tests for official FPL provider mapping."""

from __future__ import annotations

import pytest

from fpl_optimizer.data.fpl.mapper import FplMappingError, map_bootstrap, map_fixtures
from fpl_optimizer.domain.enums import FixtureStatus, Position


def test_map_bootstrap(bootstrap_payload) -> None:
    result = map_bootstrap(bootstrap_payload)

    assert len(result.teams) == 2
    assert len(result.gameweeks) == 2
    assert len(result.players) == 4
    assert result.players[1].position is Position.MIDFIELDER
    assert result.players[1].price_tenths == 95
    assert result.players[1].selected_pct == 35.5


def test_map_fixtures(fixture_payload) -> None:
    result = map_fixtures(fixture_payload)

    assert len(result) == 2
    assert result[0].status is FixtureStatus.SCHEDULED
    assert result[0].gameweek_fpl_id == 1


def test_mapping_rejects_unknown_position(bootstrap_payload) -> None:
    bootstrap_payload["elements"][0]["element_type"] = 99

    with pytest.raises(FplMappingError, match="Unknown element_type"):
        map_bootstrap(bootstrap_payload)


def test_mapping_defaults_explicitly_null_optional_metrics(bootstrap_payload) -> None:
    bootstrap_payload["teams"][0]["strength"] = None
    bootstrap_payload["elements"][0]["starts"] = None

    result = map_bootstrap(bootstrap_payload)

    assert result.teams[0].strength == 0
    assert result.players[0].starts == 0
