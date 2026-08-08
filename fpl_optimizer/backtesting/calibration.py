"""Leakage-aware chronological forecast calibration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from math import sqrt
from statistics import fmean

from fpl_optimizer.domain.backtesting import (
    AccuracyMetrics,
    BacktestObservation,
    BacktestResult,
    BlendEvaluation,
    CalibrationBand,
    PositionEvaluation,
)

WEIGHTS = tuple(index / 10 for index in range(11))


def evaluate_backtest(observations: Sequence[BacktestObservation]) -> BacktestResult:
    """Select a blend chronologically, then report untouched later-Gameweek accuracy."""

    if not observations:
        raise ValueError("No pre-deadline forecasts match the imported outcomes")
    ordered = sorted(observations, key=lambda item: (item.gameweek_id, item.player_id))
    weeks = list(dict.fromkeys((row.gameweek_id, row.gameweek) for row in ordered))
    warnings: list[str] = []
    if len(weeks) >= 4:
        split = max(1, min(len(weeks) - 1, int(len(weeks) * 0.7)))
        calibration_ids = {week_id for week_id, _ in weeks[:split]}
        calibration = [row for row in ordered if row.gameweek_id in calibration_ids]
        evaluation = [row for row in ordered if row.gameweek_id not in calibration_ids]
        mode = "chronological holdout"
    else:
        calibration = evaluation = ordered
        split = len(weeks)
        mode = "exploratory in-sample"
        warnings.append(
            "Fewer than four Gameweeks are available, so blend selection and evaluation use "
            "the same sample. Treat the recommendation as exploratory."
        )
    def predictor(weight: float) -> Callable[[BacktestObservation], float]:
        def predict(row: BacktestObservation) -> float:
            return _blend(row, weight)

        return predict

    if len(ordered) < 100:
        warnings.append("Fewer than 100 player-Gameweeks are available; error estimates may vary.")
    selected_weight = min(
        WEIGHTS,
        key=lambda weight: _metrics(calibration, predictor(weight)).rmse,
    )
    weight_results = tuple(
        BlendEvaluation(
            market_weight=weight,
            calibration_rmse=_metrics(calibration, predictor(weight)).rmse,
            metrics=_metrics(evaluation, predictor(weight)),
        )
        for weight in WEIGHTS
    )
    selected = predictor(selected_weight)
    market_rows = [row for row in evaluation if row.market_xpts is not None]
    minutes_rows = [row for row in evaluation if row.actual_minutes is not None]
    position_results = tuple(
        PositionEvaluation(position, _metrics(rows, selected))
        for position in ("GKP", "DEF", "MID", "FWD")
        if (rows := [row for row in evaluation if row.position == position])
    )
    calibration_names = tuple(name for _, name in weeks[:split])
    evaluation_names = tuple(name for _, name in weeks[split:])
    if mode != "chronological holdout":
        evaluation_names = calibration_names
    return BacktestResult(
        observations=len(ordered),
        gameweeks=len(weeks),
        calibration_gameweeks=calibration_names,
        evaluation_gameweeks=evaluation_names,
        evaluation_mode=mode,
        selected_market_weight=selected_weight,
        statistical=_metrics(evaluation, _statistical_prediction),
        market=(
            _metrics(market_rows, _market_prediction) if market_rows else None
        ),
        selected_blend=_metrics(evaluation, selected),
        expected_minutes=(
            _metrics(minutes_rows, lambda row: row.expected_minutes, actual="minutes")
            if minutes_rows
            else None
        ),
        weights=weight_results,
        positions=position_results,
        calibration_bands=_bands(evaluation, selected),
        warnings=tuple(warnings),
    )


def _blend(row: BacktestObservation, market_weight: float) -> float:
    if row.market_xpts is None:
        return row.stat_xpts
    return (1 - market_weight) * row.stat_xpts + market_weight * row.market_xpts


def _statistical_prediction(row: BacktestObservation) -> float:
    return row.stat_xpts


def _market_prediction(row: BacktestObservation) -> float:
    if row.market_xpts is None:
        raise ValueError("Market prediction requested for an uncovered observation")
    return row.market_xpts


def _metrics(
    rows: Sequence[BacktestObservation],
    prediction: Callable[[BacktestObservation], float],
    *,
    actual: str = "points",
) -> AccuracyMetrics:
    predicted = [prediction(row) for row in rows]
    realized = [
        row.actual_points if actual == "points" else float(row.actual_minutes or 0) for row in rows
    ]
    errors = [estimate - result for estimate, result in zip(predicted, realized, strict=True)]
    correlation = _correlation(predicted, realized)
    return AccuracyMetrics(
        samples=len(rows),
        mae=fmean(abs(error) for error in errors),
        rmse=sqrt(fmean(error * error for error in errors)),
        bias=fmean(errors),
        correlation=correlation,
    )


def _correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2:
        return None
    left_mean, right_mean = fmean(left), fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    left_scale = sqrt(sum((x - left_mean) ** 2 for x in left))
    right_scale = sqrt(sum((y - right_mean) ** 2 for y in right))
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def _bands(
    rows: Sequence[BacktestObservation], prediction: Callable[[BacktestObservation], float]
) -> tuple[CalibrationBand, ...]:
    definitions = (
        ("<2", -100.0, 2.0),
        ("2–4", 2.0, 4.0),
        ("4–6", 4.0, 6.0),
        ("6–8", 6.0, 8.0),
        ("8+", 8.0, 100.0),
    )
    results: list[CalibrationBand] = []
    for label, lower, upper in definitions:
        values = [(prediction(row), row.actual_points) for row in rows]
        values = [(estimate, actual) for estimate, actual in values if lower <= estimate < upper]
        if values:
            mean_prediction = fmean(value[0] for value in values)
            mean_actual = fmean(value[1] for value in values)
            results.append(
                CalibrationBand(
                    label,
                    len(values),
                    mean_prediction,
                    mean_actual,
                    mean_prediction - mean_actual,
                )
            )
    return tuple(results)
