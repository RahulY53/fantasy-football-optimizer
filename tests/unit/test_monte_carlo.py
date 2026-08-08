"""Tests for reproducible component-level team simulation."""

from __future__ import annotations

import pytest

from fpl_optimizer.domain.simulation import SimulationPlayerInput, SimulationWeekInput
from fpl_optimizer.simulation.monte_carlo import simulate_current_team


def simulation_squad() -> list[SimulationPlayerInput]:
    """Build a legal two-Gameweek squad with stable component inputs."""

    positions = ["GK"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    return [
        SimulationPlayerInput(
            player_id=index + 1,
            player=f"Player {index}",
            position=position,
            team=f"T{index % 5}",
            weeks=tuple(
                SimulationWeekInput(
                    gameweek_id=week,
                    gameweek=f"GW{week}",
                    expected_minutes=75,
                    p_appearance=0.95,
                    p_60_plus=0.8,
                    appearance_xpts=1.75,
                    goal_xpts=0.3 + index / 30,
                    assist_xpts=0.2,
                    clean_sheet_xpts=0.8 if position != "FWD" else 0.0,
                    save_xpts=0.4 if position == "GK" else 0.0,
                    bonus_xpts=0.2,
                    deduction_xpts=-0.05,
                )
                for week in (1, 2)
            ),
        )
        for index, position in enumerate(positions)
    ]


def test_simulation_is_reproducible_and_returns_complete_distributions() -> None:
    first = simulate_current_team(simulation_squad(), iterations=5_000, seed=42)
    second = simulate_current_team(simulation_squad(), iterations=5_000, seed=42)

    assert first == second
    assert first.horizon == 2
    assert first.p10 < first.median < first.p90
    assert first.standard_deviation > 0
    assert sum(bucket.count for bucket in first.histogram) == 5_000
    assert len(first.weeks) == 2
    assert all(len(week.starter_ids) == 11 for week in first.weeks)
    assert all(week.captain_id in week.starter_ids for week in first.weeks)
    assert all(0 <= player.haul_probability <= 1 for player in first.players)


def test_simulation_seed_changes_distribution_draws_but_not_expected_decisions() -> None:
    first = simulate_current_team(simulation_squad(), iterations=2_000, seed=1)
    second = simulate_current_team(simulation_squad(), iterations=2_000, seed=2)

    assert first.mean != second.mean
    assert first.weeks[0].starter_ids == second.weeks[0].starter_ids
    assert first.weeks[0].captain_id == second.weeks[0].captain_id


def test_simulation_validates_iteration_bounds() -> None:
    with pytest.raises(ValueError, match="between 1,000 and 50,000"):
        simulate_current_team(simulation_squad(), iterations=999, seed=1)
