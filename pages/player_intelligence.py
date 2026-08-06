from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from pages.player_intelligence_shared import SEGMENT_ICONS, SEGMENTS, prepare_players
from queries.player_intelligence import kpi_summary, retention_d30, vip_candidates
from ui.charts import polish
from ui.components import chart, data_table, empty_state, kpis, money, pct, period_delta
from ui.theme import page_header

MAX_SCATTER_POINTS = 1500


def render(ctx) -> None:
    page_header("PLAYER INTELLIGENCE", "Portfolio value, segmentation and CRM-safe activation lists", "Customer Intelligence")
    with st.spinner("Scoring player portfolio…"):
        players = prepare_players(ctx)
    if players.empty:
        empty_state("No players match this market")
        return

    retention = retention_d30.run(ctx)
    summary = kpi_summary.run(ctx)
    # SQLite has no percentile function: the 90th-percentile threshold is computed once from
    # the SQL-sourced column already loaded above; the KPI count itself runs as SQL.
    # Matches the KPI_REGISTRY definition ("Active non-Platinum players above the demo value
    # threshold"): both the threshold and the count are scoped to that eligible pool.
    vip_pool = players[(players.activity > 0) & (players.vip_level != "Platinum")]
    vip_threshold = vip_pool.predicted_total_ltv_180d.quantile(.90) if not vip_pool.empty else float("inf")
    vip_count = vip_candidates.run(ctx, vip_threshold)
    kpis([
        ("Observed Active Players", f"{int(summary.active_players):,}", period_delta(summary.active_players, summary.previous_active_players)),
        ("Observed Lifetime GGR", money(summary.lifetime_ggr), "All players in selected market"),
        ("Predicted Remaining LTV 90D", money(summary.remaining_ltv_90d), "Future value after the scoring date"),
        ("Predicted High Churn Risk", f"{int(summary.high_churn_risk):,}", "Active players ≥70%"),
        ("Predicted RG Interventions", f"{int(summary.rg_interventions):,}", "RG review threshold ≥55%"),
        ("Predicted VIP Candidates", f"{int(vip_count):,}", "Top 10% predicted total LTV 180D"),
        ("Observed Retention D30", pct(retention.retention_d30), f"{int(retention.retained_players or 0):,} / {int(retention.eligible_players or 0):,} eligible"),
    ], ctx, columns=4)

    st.markdown("### Portfolio segmentation")
    segment_counts = pd.DataFrame({"segment": SEGMENTS[1:], "players": [int(players[name].sum()) for name in SEGMENTS[1:]]})
    segment_cols = st.columns(4)
    for index, row in enumerate(segment_counts.itertuples()):
        with segment_cols[index % 4]:
            st.markdown(f"<div class='segment-tile'><div class='segment-icon material-symbols-rounded'>{SEGMENT_ICONS[row.segment]}</div><div><span>{row.segment}</span><strong>{row.players:,}</strong><small>Players · segments may overlap</small></div></div>", unsafe_allow_html=True)

    f1, f2 = st.columns([1.1, 1])
    with f1:
        segment_choice = st.selectbox("Business segment", SEGMENTS, key="player_360_segment")
    with f2:
        crm_safe = st.toggle("CRM-safe export only", value=True, help="Excludes fraud/RG review cases and players without verified KYC.")
    filtered = players if segment_choice == "All players" else players[players[segment_choice]]

    st.markdown("### Analyze the portfolio")
    st.caption("Open a player's full profile, risk gauges and activity timeline on the Player Profile page.")
    c1, c2 = st.columns([1, 1.3])
    with c1:
        value_by_segment = pd.DataFrame({
            "segment": SEGMENTS[1:],
            "value_at_stake": [float(players.loc[players[name], "predicted_total_ltv_180d"].sum()) for name in SEGMENTS[1:]],
        }).sort_values("value_at_stake")
        fig = px.bar(value_by_segment, x="value_at_stake", y="segment", orientation="h", color="value_at_stake",
                     title="PREDICTED VALUE AT STAKE BY SEGMENT", color_continuous_scale=[COLORS["cyan"], COLORS["gold"], COLORS["green"]])
        fig.update_layout(coloraxis_showscale=False, xaxis_title="Predicted total LTV 180D")
        chart(polish(fig, 380, False), value_by_segment, explanation="Sum of predicted total LTV 180D for players in each segment; segments may overlap.")
    with c2:
        sample = filtered if len(filtered) <= MAX_SCATTER_POINTS else filtered.sample(MAX_SCATTER_POINTS, random_state=7)
        sample = sample.assign(bubble_size=sample.lifetime_ggr.clip(lower=0) + 1)
        fig = px.scatter(
            sample, x="churn_probability", y="predicted_total_ltv_180d", color="vip_level", size="bubble_size",
            hover_data=["player_id"], title=f"RISK VS. VALUE · {segment_choice.upper()}",
            color_discrete_sequence=[COLORS["red"], COLORS["gold"], COLORS["cyan"], COLORS["green"]],
        )
        fig.add_vline(x=.70, line_dash="dash", line_color=COLORS["red"], annotation_text="High churn risk")
        fig.update_layout(xaxis_title="Predicted churn probability", xaxis_tickformat=".0%", yaxis_title="Predicted total LTV 180D")
        chart(polish(fig, 380, False), sample, explanation=f"Each point is a player in “{segment_choice}”. Bubble size is observed lifetime GGR (floored at zero); players right of the line carry the highest churn risk." + (f" Showing a random sample of {MAX_SCATTER_POINTS:,}." if len(filtered) > MAX_SCATTER_POINTS else ""))

    export = filtered[filtered.crm_eligible] if crm_safe else filtered
    export_columns = ["player_id", "country", "vip_level", "rfm_segment", "segment_tags", "lifetime_ggr", "predicted_ltv_90d", "churn_probability", "recommended_action", "model_confidence"]
    st.download_button(
        f"Export {len(export):,} players to CSV", export[export_columns].to_csv(index=False).encode("utf-8"),
        file_name=f"casino_ai_{segment_choice.lower().replace(' ', '_')}_crm.csv", mime="text/csv",
        disabled=export.empty, help="Simulated CRM activation list. No campaign is sent automatically.",
    )
    st.caption(f"{len(filtered):,} players in segment · {len(export):,} eligible for the current export guardrail.")
    if filtered.empty:
        empty_state("No players match this business segment")
        return

    portfolio = filtered[["player_id", "country", "vip_level", "rfm_segment", "segment_tags", "lifetime_ggr", "predicted_ltv_90d", "churn_probability", "fraud_risk", "rg_risk", "recommended_action"]].sort_values(["rg_risk", "churn_probability", "predicted_ltv_90d"], ascending=[False, False, False]).head(250)
    data_table(portfolio, column_config={
        "lifetime_ggr": st.column_config.NumberColumn("Observed lifetime GGR", format="$%.0f"),
        "predicted_ltv_90d": st.column_config.NumberColumn("Predicted LTV Proxy 90D", format="$%.0f"),
        "churn_probability": st.column_config.ProgressColumn("Predicted churn", min_value=0, max_value=1, format="%.1%%"),
        "fraud_risk": st.column_config.ProgressColumn("Predicted fraud", min_value=0, max_value=1, format="%.1%%"),
        "rg_risk": st.column_config.ProgressColumn("Predicted RG", min_value=0, max_value=1, format="%.1%%"),
    })
