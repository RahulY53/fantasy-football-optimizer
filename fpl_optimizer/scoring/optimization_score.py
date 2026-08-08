"""Percentile-normalized, fully decomposable player strategy score."""

from __future__ import annotations

import math
from collections import defaultdict

from fpl_optimizer.domain.strategy import (
    PlayerStrategyInput,
    PlayerStrategyScore,
    ScoreContribution,
    StrategyProfile,
)
from fpl_optimizer.scoring.normalization import normalize_weights, percentile_scores
from fpl_optimizer.scoring.presets import FEATURE_LABELS


def score_players(
    players: list[PlayerStrategyInput], profile: StrategyProfile
) -> list[PlayerStrategyScore]:
    """Score all players against one user profile and return descending results."""

    _validate_profile(profile)
    if not players:
        return []
    replacement_levels = _replacement_levels(players)
    raw_features = [
        _raw_features(player, replacement_levels, profile.risk_appetite) for player in players
    ]
    percentiles: list[dict[str, float]] = [dict() for _ in players]
    feature_names = set().union(*(features.keys() for features in raw_features))
    for feature in feature_names:
        ranked = percentile_scores([features[feature] for features in raw_features])
        for index, value in enumerate(ranked):
            percentiles[index][feature] = value

    effective_weights = {key: float(value) for key, value in profile.weights.items()}
    if profile.ownership_preference:
        effective_weights["ownership_fit"] = abs(float(profile.ownership_preference))
        ownership_percentiles = percentile_scores([player.ownership for player in players])
        for index, percentile in enumerate(ownership_percentiles):
            percentiles[index]["ownership_fit"] = (
                percentile if profile.ownership_preference > 0 else 100.0 - percentile
            )
            raw_features[index]["ownership_fit"] = players[index].ownership
    normalized = normalize_weights(effective_weights)

    scored: list[PlayerStrategyScore] = []
    for player, raw, normalized_features in zip(
        players, raw_features, percentiles, strict=True
    ):
        contributions = tuple(
            ScoreContribution(
                feature=feature,
                label=FEATURE_LABELS[feature],
                raw_value=raw[feature],
                percentile=normalized_features[feature],
                raw_weight=effective_weights[feature],
                normalized_weight=normalized_weight,
                contribution=normalized_features[feature] * normalized_weight,
            )
            for feature, normalized_weight in normalized.items()
        )
        scored.append(
            PlayerStrategyScore(
                player_id=player.player_id,
                player=player.player,
                position=player.position,
                team=player.team,
                price=player.price,
                ownership=player.ownership,
                horizon_xpts=player.horizon_xpts,
                value=raw["value"],
                risk=raw["risk_level"],
                score=sum(item.contribution for item in contributions),
                contributions=contributions,
            )
        )
    return sorted(scored, key=lambda item: (-item.score, -item.horizon_xpts, item.player))


def strategy_summary(profile: StrategyProfile) -> str:
    """Generate a deterministic plain-language description of a profile."""

    ordered = sorted(profile.weights.items(), key=lambda item: item[1], reverse=True)
    strong = [FEATURE_LABELS[key].lower() for key, value in ordered if value >= 75][:3]
    moderate = [FEATURE_LABELS[key].lower() for key, value in ordered if 40 <= value < 75][:2]
    ignored = [FEATURE_LABELS[key].lower() for key, value in ordered if value <= 20][:2]
    parts = [
        "Your strategy strongly prioritizes " + _join_words(strong)
        if strong
        else "Your strategy uses broadly even priorities"
    ]
    if moderate:
        parts.append("moderately values " + _join_words(moderate))
    if ignored:
        parts.append("places relatively little emphasis on " + _join_words(ignored))
    risk_text = (
        "prefers predictable players"
        if profile.risk_appetite < 35
        else "accepts volatile upside"
        if profile.risk_appetite > 65
        else "takes a balanced view of risk"
    )
    ownership_text = (
        "leans toward differentials"
        if profile.ownership_preference < -25
        else "leans toward template players"
        if profile.ownership_preference > 25
        else "is mostly ownership-neutral"
    )
    return "; ".join(parts) + f". It {risk_text} and {ownership_text}."


def _raw_features(
    player: PlayerStrategyInput,
    replacement_levels: dict[str, float],
    risk_appetite: int,
) -> dict[str, float]:
    replacement = replacement_levels[player.position]
    mean = player.horizon_xpts / max(len(player.week_xpts), 1)
    variance = (
        sum((value - mean) ** 2 for value in player.week_xpts) / len(player.week_xpts)
        if player.week_xpts
        else 0.0
    )
    consistency = 1.0 / (1.0 + math.sqrt(variance))
    rotation_safety = max(0.0, min(player.expected_minutes / 90.0, 1.0))
    injury_safety = _injury_safety(player.status, player.chance_next_round)
    base_safety = 100.0 * (
        0.45 * rotation_safety + 0.35 * injury_safety + 0.20 * player.confidence
    )
    risk_fit = base_safety * (1.0 - risk_appetite / 100.0) + 50.0 * (
        risk_appetite / 100.0
    )
    return {
        "expected_points": player.horizon_xpts,
        "fixtures": player.fixture_quality,
        "expected_minutes": player.expected_minutes,
        "form": player.form,
        "value": player.horizon_xpts / max(player.price, 0.1),
        "vorp": player.horizon_xpts - replacement,
        "attacking": player.attacking_xpts,
        "clean_sheet": player.clean_sheet_xpts,
        "bonus": player.bonus_xpts,
        "differential": 100.0 - player.ownership,
        "ceiling": max(player.week_xpts, default=0.0) + 0.25 * player.attacking_xpts,
        "consistency": consistency,
        "risk": risk_fit,
        "risk_level": 100.0 - base_safety,
        "rotation_safety": 100.0 * rotation_safety,
        "injury_safety": 100.0 * injury_safety,
    }


def _replacement_levels(players: list[PlayerStrategyInput]) -> dict[str, float]:
    by_position: dict[str, list[float]] = defaultdict(list)
    for player in players:
        by_position[player.position].append(player.horizon_xpts)
    levels: dict[str, float] = {}
    for position, values in by_position.items():
        ordered = sorted(values)
        levels[position] = ordered[max(0, int(0.25 * (len(ordered) - 1)))]
    return levels


def _injury_safety(status: str, chance: int | None) -> float:
    if chance is not None:
        return max(0.0, min(chance / 100.0, 1.0))
    return 1.0 if status == "a" else 0.65 if status == "d" else 0.2


def _validate_profile(profile: StrategyProfile) -> None:
    if profile.mode not in {"simple", "advanced"}:
        raise ValueError("Strategy mode must be simple or advanced")
    if not 1 <= profile.horizon <= 6:
        raise ValueError("Planning horizon must be between 1 and 6 Gameweeks")
    if not 0 <= profile.risk_appetite <= 100:
        raise ValueError("Risk appetite must be between 0 and 100")
    if not -100 <= profile.ownership_preference <= 100:
        raise ValueError("Ownership preference must be between -100 and 100")
    unknown = set(profile.weights) - set(FEATURE_LABELS)
    if unknown:
        raise ValueError(f"Unknown strategy features: {', '.join(sorted(unknown))}")
    if any(value > 100 for value in profile.weights.values()):
        raise ValueError("Strategy weights cannot exceed 100")
    normalize_weights({key: float(value) for key, value in profile.weights.items()})


def _join_words(values: list[str]) -> str:
    if len(values) < 2:
        return values[0] if values else ""
    return ", ".join(values[:-1]) + f" and {values[-1]}"
