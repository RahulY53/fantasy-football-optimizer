"""Plotly forecast trend charts for selected-player analytics."""

from __future__ import annotations

from typing import Literal

import plotly.graph_objects as go

from fpl_optimizer.analytics.forecast_comparison import ForecastComparison

ForecastChartMode = Literal["Weekly xPts", "Cumulative xPts"]


def player_forecast_figure(
    comparison: ForecastComparison,
    mode: ForecastChartMode,
) -> go.Figure:
    """Build an interactive raw-points chart for selected players."""

    figure = go.Figure()
    cumulative = mode == "Cumulative xPts"
    for player in comparison.series:
        values = [
            point.cumulative_xpts if cumulative else point.blended_xpts
            for point in player.points
        ]
        customdata = [
            [
                player.team,
                player.position,
                point.opponent,
                point.expected_minutes,
                point.stat_xpts,
                f"{point.market_xpts:.2f}" if point.market_xpts is not None else "Unavailable",
                point.blended_xpts,
                point.cumulative_xpts,
                point.confidence,
            ]
            for point in player.points
        ]
        figure.add_trace(
            go.Scatter(
                x=[point.gameweek for point in player.points],
                y=values,
                name=player.full_name,
                mode="lines+markers",
                marker={"size": 9},
                line={"width": 3},
                customdata=customdata,
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "%{x}<br>"
                    "Team: %{customdata[0]} · %{customdata[1]}<br>"
                    "Opponent: %{customdata[2]}<br>"
                    "Expected minutes: %{customdata[3]:.0f}<br>"
                    "Stat xPts: %{customdata[4]:.2f}<br>"
                    "Market xPts: %{customdata[5]}<br>"
                    "Blended xPts: %{customdata[6]:.2f}<br>"
                    "Cumulative xPts: %{customdata[7]:.2f}<br>"
                    "Confidence: %{customdata[8]}"
                    "<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        height=510,
        margin={"l": 24, "r": 18, "t": 30, "b": 30},
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.18, "x": 0.5, "xanchor": "center"},
        xaxis={"title": "Future Gameweek", "type": "category"},
        yaxis={
            "title": "Cumulative blended xPts" if cumulative else "Blended xPts",
            "rangemode": "tozero",
        },
        template="plotly_white",
    )
    return figure
