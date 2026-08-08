"""Plotly presentation for normalized player radar profiles."""

from __future__ import annotations

import plotly.graph_objects as go

from fpl_optimizer.analytics.comparison import PlayerRadarProfile

COLORS = ("#2563EB", "#DC2626", "#16A34A", "#9333EA", "#EA580C")


def player_radar_figure(profiles: tuple[PlayerRadarProfile, ...]) -> go.Figure:
    """Create a responsive radar chart with normalized scores and raw-value hover."""

    figure = go.Figure()
    for index, profile in enumerate(profiles):
        scores = [metric.score for metric in profile.metrics]
        labels = [metric.label for metric in profile.metrics]
        raw_values = [metric.formatted_value for metric in profile.metrics]
        figure.add_trace(
            go.Scatterpolar(
                r=[*scores, scores[0]],
                theta=[*labels, labels[0]],
                customdata=[[value] for value in [*raw_values, raw_values[0]]],
                fill="toself",
                fillcolor=_rgba(COLORS[index], 0.10),
                line={"color": COLORS[index], "width": 3},
                marker={"color": COLORS[index], "size": 7},
                name=f"{profile.full_name} · {profile.team}",
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "%{theta}<br>"
                    "Favorable percentile: %{r:.0f}/100<br>"
                    "Raw value: %{customdata[0]}"
                    "<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        height=600,
        margin={"l": 55, "r": 55, "t": 35, "b": 100},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 100],
                "tickvals": [0, 25, 50, 75, 100],
                "ticksuffix": "",
            },
            "angularaxis": {"direction": "clockwise"},
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.14,
            "xanchor": "center",
            "x": 0.5,
        },
        hovermode="closest",
    )
    return figure


def _rgba(hex_color: str, alpha: float) -> str:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return f"rgba({red},{green},{blue},{alpha})"
