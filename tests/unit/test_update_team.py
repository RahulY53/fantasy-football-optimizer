"""Tests for the one-action team update orchestration and odds fallback."""

from __future__ import annotations

from types import SimpleNamespace

from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.services.update_team import TeamUpdateService


class _Service:
    def __init__(self, name: str, calls: list[str], result: object) -> None:
        self.name = name
        self.calls = calls
        self.result = result

    def refresh(self, force: bool = False):
        self.calls.append(self.name)
        return self.result

    def import_team(self, team_id: int, force: bool = False):
        self.calls.append(f"{self.name}:{team_id}:{force}")
        return self.result

    def run(self, *args, **kwargs):
        self.calls.append(self.name)
        return self.result

    def optimize(self, *args, **kwargs):
        self.calls.append(self.name)
        return self.result


def test_one_action_update_runs_inputs_before_optimizers() -> None:
    calls: list[str] = []
    refresh_result = SimpleNamespace(warnings=("cached FPL",))
    odds_result = SimpleNamespace(warnings=("one event rejected",))
    service = TeamUpdateService(
        _Service("refresh", calls, refresh_result),  # type: ignore[arg-type]
        _Service("import", calls, object()),  # type: ignore[arg-type]
        _Service("forecast", calls, object()),  # type: ignore[arg-type]
        _Service("odds", calls, odds_result),  # type: ignore[arg-type]
        _Service("lineup", calls, object()),  # type: ignore[arg-type]
        _Service("transfers", calls, object()),  # type: ignore[arg-type]
    )
    profile = StrategyProfile("Test", "simple", "Test", 3, 40, 50, 0, {})

    report = service.run(42, profile, 0.3)

    assert calls == ["refresh", "import:42:True", "forecast", "odds", "lineup", "transfers"]
    assert report.warnings == ("cached FPL", "one event rejected")


class _FailingOdds(_Service):
    def refresh(self, force: bool = False):
        self.calls.append(self.name)
        raise RuntimeError("quota unavailable")


def test_one_action_update_continues_when_live_odds_fail() -> None:
    calls: list[str] = []
    service = TeamUpdateService(
        _Service("refresh", calls, SimpleNamespace(warnings=())),  # type: ignore[arg-type]
        _Service("import", calls, object()),  # type: ignore[arg-type]
        _Service("forecast", calls, object()),  # type: ignore[arg-type]
        _FailingOdds("odds", calls, object()),  # type: ignore[arg-type]
        _Service("lineup", calls, object()),  # type: ignore[arg-type]
        _Service("transfers", calls, object()),  # type: ignore[arg-type]
    )
    profile = StrategyProfile("Test", "simple", "Test", 3, 40, 50, 0, {})

    report = service.run(42, profile, 0.3)

    assert report.odds is None
    assert "statistical forecast only" in report.warnings[0]
    assert calls[-2:] == ["lineup", "transfers"]
