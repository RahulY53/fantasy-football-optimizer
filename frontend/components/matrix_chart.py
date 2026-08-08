"""Interactive Plotly presentation for raw-metric player matrices."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

import plotly.graph_objects as go
from plotly.colors import qualitative

from fpl_optimizer.analytics.matrix import MatrixAnalysis, MatrixPoint

ColorMode = Literal["None", "Team", "Position", "Risk category"]
SizeMode = Literal["Fixed", "Price", "Ownership", "Blended xPts", "Optimization Score"]
LabelMode = Literal["Selected names", "Top N", "All names", "Hide names"]


def player_matrix_figure(
    analysis: MatrixAnalysis,
    *,
    color_mode: ColorMode,
    size_mode: SizeMode,
    label_mode: LabelMode,
    highlighted_ids: frozenset[int] = frozenset(),
    top_n: int = 10,
) -> go.Figure:
    """Create a responsive raw-axis scatter with quadrant and hover context."""

    labelled_ids = _labelled_ids(analysis.points, label_mode, highlighted_ids, top_n)
    sizes = _point_sizes(analysis.points, size_mode)
    grouped: dict[str, list[tuple[MatrixPoint, float]]] = defaultdict(list)
    for point, size in zip(analysis.points, sizes, strict=True):
        grouped[_group(point, color_mode)].append((point, size))

    figure = go.Figure()
    palette = qualitative.Alphabet
    for index, (group, values) in enumerate(sorted(grouped.items())):
        points = [item[0] for item in values]
        marker_sizes = [item[1] for item in values]
        color = palette[index % len(palette)]
        figure.add_trace(
            go.Scatter(
                x=[point.x_value for point in points],
                y=[point.y_value for point in points],
                mode="markers+text",
                name=group,
                showlegend=color_mode != "None",
                text=[
                    point.full_name if point.player_id in labelled_ids else "" for point in points
                ],
                textposition="top center",
                textfont={"size": 10},
                customdata=[
                    [
                        point.full_name,
                        point.team,
                        point.position,
                        f"£{point.price:.1f}m",
                        point.x_formatted,
                        point.y_formatted,
                        _optional(point.blended_xpts, "{:.1f}"),
                        _optional(point.expected_minutes, "{:.0f}"),
                        f"{point.ownership:.1f}%",
                        _optional(point.risk, "{:.0f}/100"),
                        _optional(point.optimization_score, "{:.1f}"),
                    ]
                    for point in points
                ],
                marker={
                    "size": marker_sizes,
                    "color": color,
                    "opacity": 0.82,
                    "line": {
                        "color": [
                            "#111827" if point.player_id in highlighted_ids else "white"
                            for point in points
                        ],
                        "width": [
                            3 if point.player_id in highlighted_ids else 1 for point in points
                        ],
                    },
                },
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "%{customdata[1]} · %{customdata[2]} · %{customdata[3]}<br>"
                    f"{analysis.x_metric.label}: %{{customdata[4]}}<br>"
                    f"{analysis.y_metric.label}: %{{customdata[5]}}<br>"
                    "Blended xPts: %{customdata[6]}<br>"
                    "Expected minutes: %{customdata[7]}<br>"
                    "Ownership: %{customdata[8]}<br>"
                    "Risk: %{customdata[9]}<br>"
                    "Optimization score: %{customdata[10]}"
                    "<extra></extra>"
                ),
            )
        )

    figure.add_vline(
        x=analysis.x_reference,
        line_dash="dash",
        line_color="#475569",
        annotation_text=(
            f"{analysis.reference_method}: {analysis.x_metric.format_value(analysis.x_reference)}"
        ),
        annotation_position="top left",
    )
    figure.add_hline(
        y=analysis.y_reference,
        line_dash="dash",
        line_color="#475569",
        annotation_text=(
            f"{analysis.reference_method}: {analysis.y_metric.format_value(analysis.y_reference)}"
        ),
        annotation_position="bottom right",
    )
    if analysis.diagonal:
        shared_min = min(
            min(point.x_value for point in analysis.points),
            min(point.y_value for point in analysis.points),
        )
        shared_max = max(
            max(point.x_value for point in analysis.points),
            max(point.y_value for point in analysis.points),
        )
        figure.add_shape(
            type="line",
            x0=shared_min,
            y0=shared_min,
            x1=shared_max,
            y1=shared_max,
            line={"color": "#0F766E", "dash": "dot", "width": 2},
        )
        figure.add_annotation(
            x=shared_max,
            y=shared_max,
            text="Market = Model",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
            font={"color": "#0F766E", "size": 11},
        )

    _add_quadrant_labels(figure, analysis)
    x_unit = f" ({analysis.x_metric.unit})" if analysis.x_metric.unit else ""
    y_unit = f" ({analysis.y_metric.unit})" if analysis.y_metric.unit else ""
    figure.update_layout(
        height=650,
        margin={"l": 60, "r": 35, "t": 55, "b": 120},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        xaxis={
            "title": f"{analysis.x_metric.label}{x_unit}",
            "showgrid": True,
            "zeroline": False,
        },
        yaxis={
            "title": f"{analysis.y_metric.label}{y_unit}",
            "showgrid": True,
            "zeroline": False,
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.18,
            "xanchor": "center",
            "x": 0.5,
        },
    )
    return figure


def _group(point: MatrixPoint, mode: ColorMode) -> str:
    if mode == "Team":
        return point.team
    if mode == "Position":
        return point.position
    if mode == "Risk category":
        if point.risk is None:
            return "Risk unavailable"
        if point.risk <= 33:
            return "Low risk"
        if point.risk <= 66:
            return "Medium risk"
        return "High risk"
    return "Players"


def _point_sizes(points: tuple[MatrixPoint, ...], mode: SizeMode) -> list[float]:
    if mode == "Fixed":
        return [14.0 for _ in points]
    values = [
        {
            "Price": point.price,
            "Ownership": point.ownership,
            "Blended xPts": point.blended_xpts or 0.0,
            "Optimization Score": point.optimization_score or 0.0,
        }[mode]
        for point in points
    ]
    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        return [18.0 for _ in values]
    return [10.0 + 24.0 * (value - minimum) / (maximum - minimum) for value in values]


def _labelled_ids(
    points: tuple[MatrixPoint, ...],
    mode: LabelMode,
    highlighted_ids: frozenset[int],
    top_n: int,
) -> frozenset[int]:
    if mode == "All names":
        return frozenset(point.player_id for point in points)
    if mode == "Selected names":
        return highlighted_ids
    if mode == "Hide names":
        return frozenset()
    ranked = sorted(
        points,
        key=lambda point: (point.optimization_score or 0.0, point.y_value),
        reverse=True,
    )
    return frozenset(point.player_id for point in ranked[:top_n])


def _add_quadrant_labels(figure: go.Figure, analysis: MatrixAnalysis) -> None:
    x_values = [point.x_value for point in analysis.points]
    y_values = [point.y_value for point in analysis.points]
    x_min = min(min(x_values), analysis.x_reference)
    x_max = max(max(x_values), analysis.x_reference)
    y_min = min(min(y_values), analysis.y_reference)
    y_max = max(max(y_values), analysis.y_reference)
    locations = (
        ((x_min + analysis.x_reference) / 2, (analysis.y_reference + y_max) / 2, "upper_left"),
        ((analysis.x_reference + x_max) / 2, (analysis.y_reference + y_max) / 2, "upper_right"),
        ((x_min + analysis.x_reference) / 2, (y_min + analysis.y_reference) / 2, "lower_left"),
        ((analysis.x_reference + x_max) / 2, (y_min + analysis.y_reference) / 2, "lower_right"),
    )
    for x_value, y_value, key in locations:
        figure.add_annotation(
            x=x_value,
            y=y_value,
            text=analysis.labels.label(key),  # type: ignore[arg-type]
            showarrow=False,
            opacity=0.32,
            font={"size": 10, "color": "#334155"},
        )


def _optional(value: float | None, format_string: str) -> str:
    return "Unavailable" if value is None else format_string.format(value)
