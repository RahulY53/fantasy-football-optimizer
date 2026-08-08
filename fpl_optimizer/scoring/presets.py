"""Built-in strategy presets and display metadata."""

from __future__ import annotations

from typing import cast

from fpl_optimizer.domain.strategy import StrategyProfile

FEATURE_LABELS = {
    "expected_points": "Expected points",
    "fixtures": "Fixtures",
    "expected_minutes": "Expected minutes",
    "form": "Form",
    "value": "Value",
    "vorp": "Value above replacement",
    "attacking": "Attacking potential",
    "clean_sheet": "Clean-sheet potential",
    "bonus": "Bonus potential",
    "differential": "Differential potential",
    "ceiling": "Ceiling",
    "consistency": "Consistency",
    "risk": "Downside protection",
    "rotation_safety": "Rotation safety",
    "injury_safety": "Injury safety",
    "ownership_fit": "Ownership preference",
}

SIMPLE_FEATURES = (
    "expected_points",
    "fixtures",
    "form",
    "value",
    "risk",
    "differential",
)

ADVANCED_FEATURES = (
    "expected_points",
    "fixtures",
    "expected_minutes",
    "form",
    "value",
    "vorp",
    "attacking",
    "clean_sheet",
    "bonus",
    "differential",
    "ceiling",
    "consistency",
    "rotation_safety",
    "injury_safety",
)

_BALANCED = {
    "expected_points": 90,
    "fixtures": 60,
    "expected_minutes": 75,
    "form": 35,
    "value": 45,
    "vorp": 45,
    "attacking": 50,
    "clean_sheet": 40,
    "bonus": 25,
    "differential": 20,
    "ceiling": 45,
    "consistency": 50,
    "risk": 65,
    "rotation_safety": 65,
    "injury_safety": 65,
}

PRESETS: dict[str, dict[str, object]] = {
    "Balanced": {"risk": 40, "ownership": 10, "weights": _BALANCED},
    "Conservative": {
        "risk": 15,
        "ownership": 45,
        "weights": {
            **_BALANCED,
            "expected_minutes": 95,
            "consistency": 85,
            "risk": 95,
            "rotation_safety": 95,
            "injury_safety": 100,
            "ceiling": 20,
            "differential": 5,
        },
    },
    "Aggressive": {
        "risk": 80,
        "ownership": -25,
        "weights": {
            **_BALANCED,
            "attacking": 80,
            "ceiling": 100,
            "differential": 70,
            "consistency": 15,
            "risk": 20,
            "rotation_safety": 20,
            "injury_safety": 25,
        },
    },
    "Value Hunter": {
        "risk": 45,
        "ownership": -10,
        "weights": {**_BALANCED, "value": 100, "vorp": 100, "expected_points": 70},
    },
    "Differential": {
        "risk": 70,
        "ownership": -85,
        "weights": {
            **_BALANCED,
            "differential": 100,
            "ceiling": 85,
            "attacking": 70,
            "risk": 25,
        },
    },
    "Short-Term Attack": {
        "risk": 65,
        "ownership": -20,
        "horizon": 2,
        "weights": {
            **_BALANCED,
            "expected_points": 100,
            "fixtures": 90,
            "attacking": 95,
            "ceiling": 80,
        },
    },
    "Long-Term Planner": {
        "risk": 35,
        "ownership": 10,
        "horizon": 6,
        "weights": {
            **_BALANCED,
            "expected_points": 100,
            "fixtures": 80,
            "consistency": 75,
            "expected_minutes": 85,
        },
    },
}


def preset_profile(name: str, mode: str = "simple") -> StrategyProfile:
    """Build a validated profile from a named built-in preset."""

    if name not in PRESETS:
        raise ValueError(f"Unknown strategy preset: {name}")
    if mode not in {"simple", "advanced"}:
        raise ValueError("Strategy mode must be simple or advanced")
    preset = PRESETS[name]
    all_weights = cast(dict[str, int], preset["weights"])
    features = SIMPLE_FEATURES if mode == "simple" else ADVANCED_FEATURES
    return StrategyProfile(
        name=name,
        mode=mode,  # type: ignore[arg-type]
        preset=name,
        horizon=cast(int, preset.get("horizon", 3)),
        risk_appetite=cast(int, preset["risk"]),
        transfer_reluctance=50,
        ownership_preference=cast(int, preset["ownership"]),
        weights={feature: all_weights[feature] for feature in features},
    )
