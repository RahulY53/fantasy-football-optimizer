"""User-controlled strategy scoring and explainability dashboard."""

from __future__ import annotations

from dataclasses import asdict, replace

import pandas as pd
import streamlit as st
from shared import market_weight, page_setup

from fpl_optimizer.domain.strategy import StrategyProfile
from fpl_optimizer.scoring.normalization import normalize_weights
from fpl_optimizer.scoring.optimization_score import strategy_summary
from fpl_optimizer.scoring.presets import (
    ADVANCED_FEATURES,
    FEATURE_LABELS,
    PRESETS,
    SIMPLE_FEATURES,
    preset_profile,
)

container = page_setup("Strategy", "🎛️")
st.title("Strategy")
st.caption("Express decision preferences without changing the underlying player forecasts")

st.subheader("Forecast model")
forecast_cols = st.columns(3)
forecast_cols[0].metric("Statistical model", f"{(1.0 - market_weight()):.0%}")
forecast_cols[1].metric("Betting market model", f"{market_weight():.0%}")
forecast_cols[2].caption("Adjust Market influence in the sidebar. This changes predictions.")

st.divider()
st.subheader("Strategy settings")
mode = st.radio("Mode", ["Simple", "Advanced"], horizontal=True).lower()
preset_name = st.selectbox("Preset", list(PRESETS))
base = preset_profile(preset_name, mode)

settings_cols = st.columns(4)
horizon = settings_cols[0].slider(
    "Planning horizon",
    1,
    6,
    base.horizon,
    key=f"horizon_{mode}_{preset_name}",
    help="The number of future Gameweeks included in the decision score.",
)
risk_appetite = settings_cols[1].slider(
    "Risk appetite",
    0,
    100,
    base.risk_appetite,
    key=f"risk_appetite_{mode}_{preset_name}",
    help="Higher values tolerate uncertain minutes and volatility; they do not alter xPts.",
)
transfer_reluctance = settings_cols[2].slider(
    "Transfer reluctance",
    0,
    100,
    base.transfer_reluctance,
    key=f"transfer_reluctance_{mode}_{preset_name}",
    help="Sets the gain required to spend a transfer; it does not alter xPts or this ranking.",
)
ownership_preference = settings_cols[3].slider(
    "Ownership preference",
    -100,
    100,
    base.ownership_preference,
    key=f"ownership_{mode}_{preset_name}",
    help="Negative prefers differentials, zero ignores ownership, positive prefers template picks.",
)

st.markdown("#### Feature weights")
st.caption("Set importance from 0 to 100. Weights are normalized automatically.")
features = SIMPLE_FEATURES if mode == "simple" else ADVANCED_FEATURES
weight_columns = st.columns(3)
weights: dict[str, int] = {}
for index, feature in enumerate(features):
    weights[feature] = weight_columns[index % 3].slider(
        FEATURE_LABELS[feature],
        0,
        100,
        base.weights[feature],
        key=f"weight_{mode}_{preset_name}_{feature}",
    )

profile = StrategyProfile(
    name="Working strategy",
    mode=mode,  # type: ignore[arg-type]
    preset=preset_name,
    horizon=horizon,
    risk_appetite=risk_appetite,
    transfer_reluctance=transfer_reluctance,
    ownership_preference=ownership_preference,
    weights=weights,
)
st.session_state["active_strategy"] = asdict(profile)

effective_weights = {feature: float(value) for feature, value in weights.items()}
if ownership_preference:
    effective_weights["ownership_fit"] = abs(float(ownership_preference))
try:
    normalized = normalize_weights(effective_weights)
except ValueError as error:
    st.error(str(error))
    st.stop()

with st.expander("Raw and normalized weights"):
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Feature": FEATURE_LABELS[feature],
                    "Raw weight": effective_weights[feature],
                    "Normalized weight": normalized.get(feature, 0.0) * 100,
                }
                for feature in effective_weights
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Normalized weight": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

st.info(strategy_summary(profile))

scores = container.strategy.score(profile, market_weight())
if not scores:
    st.warning("Generate statistical forecasts before calculating strategy scores.")
else:
    st.subheader("Player optimization scores")
    ranking = pd.DataFrame(
        [
            {
                "Rank": rank,
                "Player ID": score.player_id,
                "Player": score.player,
                "Position": score.position,
                "Team": score.team,
                "Price": score.price,
                f"{horizon}GW xPts": score.horizon_xpts,
                "Ownership %": score.ownership,
                "Value": score.value,
                "Risk": score.risk,
                "Optimization Score": score.score,
            }
            for rank, score in enumerate(scores, start=1)
        ]
    )
    st.dataframe(
        ranking,
        hide_index=True,
        width="stretch",
        column_config={
            "Price": st.column_config.NumberColumn(format="£%.1fm"),
            f"{horizon}GW xPts": st.column_config.NumberColumn(format="%.1f"),
            "Ownership %": st.column_config.NumberColumn(format="%.1f%%"),
            "Value": st.column_config.NumberColumn(format="%.1f"),
            "Risk": st.column_config.NumberColumn(format="%.0f/100"),
            "Optimization Score": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f"
            ),
        },
        column_order=(
            "Rank",
            "Player",
            "Position",
            "Team",
            "Price",
            f"{horizon}GW xPts",
            "Ownership %",
            "Value",
            "Risk",
            "Optimization Score",
        ),
    )

    st.subheader("Score contribution breakdown")
    labels = {
        score.player_id: f"{score.player} · {score.team} · {score.score:.1f}"
        for score in scores
    }
    selected_id = st.selectbox(
        "Player",
        options=list(labels),
        format_func=lambda player_id: labels[player_id],
        key="strategy_player",
    )
    selected = next(score for score in scores if score.player_id == selected_id)
    contribution_frame = pd.DataFrame(
        [
            {
                "Feature": item.label,
                "Raw value": item.raw_value,
                "Percentile": item.percentile,
                "Raw weight": item.raw_weight,
                "Normalized weight": item.normalized_weight * 100,
                "Contribution": item.contribution,
            }
            for item in selected.contributions
        ]
    ).sort_values("Contribution", ascending=False)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Optimization score", f"{selected.score:.1f}/100")
    metric_cols[1].metric("Projected points", f"{selected.horizon_xpts:.1f}")
    metric_cols[2].metric("Planning horizon", f"{horizon} GW")
    st.bar_chart(contribution_frame.set_index("Feature")["Contribution"])
    st.dataframe(
        contribution_frame,
        hide_index=True,
        width="stretch",
        column_config={
            "Raw value": st.column_config.NumberColumn(format="%.1f"),
            "Percentile": st.column_config.NumberColumn(format="%.1f"),
            "Normalized weight": st.column_config.NumberColumn(format="%.1f%%"),
            "Contribution": st.column_config.NumberColumn(format="%+.1f"),
        },
    )
    st.caption("Contributions sum exactly to the displayed optimization score.")

st.divider()
st.subheader("Save custom strategy")
save_cols = st.columns([2, 1, 2])
custom_name = save_cols[0].text_input("Strategy name", placeholder="My deadline strategy")
if save_cols[1].button("Save strategy", type="primary", width="stretch"):
    try:
        strategy_id = container.strategy.save(replace(profile, name=custom_name.strip()))
        st.success(f"Saved strategy #{strategy_id}: {custom_name.strip()}")
    except ValueError as error:
        st.error(str(error))

saved = container.strategy.list_saved()
if saved:
    with st.expander(f"Saved strategies ({len(saved)})"):
        st.dataframe(
            pd.DataFrame(saved).drop(columns=["Weights"]),
            hide_index=True,
            width="stretch",
        )
