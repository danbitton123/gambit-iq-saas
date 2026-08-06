from __future__ import annotations

from hashlib import sha256

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from pages.player_intelligence_shared import SEGMENTS, prepare_players
from queries.player_intelligence import favorite_games, player_timeline
from ui.charts import polish
from ui.components import chart, data_table, empty_state, money, pct
from ui.theme import page_header


FACT_ICONS = {
    "ggr": "paid", "ltv": "query_stats", "deposit": "account_balance_wallet", "withdraw": "payments",
    "cash": "currency_exchange", "bonus": "confirmation_number", "first": "event_available", "casino": "casino",
    "sportsbook": "sports_soccer", "favorite": "star", "frequency": "pace", "last activity": "history",
    "rfm": "category", "wagered": "toll", "churn": "person_remove", "fraud": "gpp_maybe",
    "rg": "health_and_safety", "campaign": "campaign", "activation": "verified_user", "session": "schedule",
}


def _stable_number(player_id: str, salt: str, minimum: int, maximum: int) -> int:
    digest = sha256(f"{player_id}:{salt}".encode()).hexdigest()
    return minimum + int(digest[:8], 16) % (maximum - minimum + 1)


def _fact_icon(label: str) -> str:
    normalized = label.lower()
    return next((icon for keyword, icon in FACT_ICONS.items() if keyword in normalized), "analytics")


def _profile_fact(label: str, value: str, note: str = "", icon: str | None = None) -> None:
    st.markdown(
        f"<div class='player-fact'><div class='player-fact-icon material-symbols-rounded'>{icon or _fact_icon(label)}</div>"
        f"<div class='player-fact-copy'><span>{label}</span><strong>{value}</strong><small>{note}</small></div></div>",
        unsafe_allow_html=True,
    )


def render(ctx) -> None:
    page_header("PLAYER PROFILE", "Individual value, behavior, risk and activation drill-down", "Customer Intelligence")
    players = prepare_players(ctx)
    if players.empty:
        empty_state("No players match this market")
        return

    st.markdown("### Find a player")
    f1, f2 = st.columns([1.1, 1])
    with f1:
        segment_choice = st.selectbox("Business segment", SEGMENTS, key="player_profile_segment")
    filtered = players if segment_choice == "All players" else players[players[segment_choice]]
    if filtered.empty:
        empty_state("No players match this business segment")
        return
    with f2:
        selected = st.selectbox("Search anonymized player ID", filtered.player_id.tolist(), key="player_profile_selected")

    player = players.loc[players.player_id == selected].iloc[0]
    status = "CRM eligible" if player.crm_eligible else "Suppressed from CRM"
    st.markdown(
        f"<section class='player-identity'><div class='player-avatar material-symbols-rounded'>person</div>"
        f"<div class='player-identity-main'><span class='identity-eyebrow'>PLAYER PROFILE</span><h3>{selected}</h3>"
        f"<div class='identity-attributes'>"
        f"<span><i class='material-symbols-rounded'>public</i>{player.country}</span>"
        f"<span><i class='material-symbols-rounded'>workspace_premium</i>{player.vip_level}</span>"
        f"<span><i class='material-symbols-rounded'>category</i>{player.rfm_segment}</span>"
        f"<span><i class='material-symbols-rounded'>conversion_path</i>{player.channel}</span>"
        f"<span><i class='material-symbols-rounded'>smartphone</i>{player.device}</span></div></div>"
        f"<div class='identity-status'><strong class={'identity-good' if player.crm_eligible else 'identity-risk'}>"
        f"<i class='material-symbols-rounded'>{'verified' if player.crm_eligible else 'block'}</i>{status}</strong>"
        f"<small>{player.recommended_action}</small></div></section>", unsafe_allow_html=True,
    )

    value_tab, behavior_tab, risk_tab, timeline_tab, crm_tab = st.tabs(["Value & cash", "Gaming behavior", "Risk & RG", "Timeline", "CRM history"])
    with value_tab:
        cols = st.columns(4)
        facts = [
            ("Observed lifetime GGR", money(player.lifetime_ggr, False), "Casino + sportsbook"),
            ("Observed value", money(player.observed_value, False), "Value measured before scoring"),
            ("Predicted remaining LTV 90D", money(player.remaining_ltv_90d, False), "Future value after scoring"),
            ("Predicted total LTV 180D", money(player.predicted_total_ltv_180d, False), "Observed + remaining predicted value"),
            ("Observed deposits", money(player.deposits, False), f"{int(player.deposit_count):,} approved deposits"),
            ("Observed withdrawals", money(player.withdrawals, False), "Approved transactions"),
            ("Observed period GGR", money(player.period_ggr, False), ctx.period_label),
            ("Observed net cash flow", money(player.deposits-player.withdrawals, False), "Deposits − withdrawals"),
            ("First approved deposit", f"{pd.Timestamp(player.ftd_date):%d %b %Y}" if pd.notna(player.ftd_date) else "No FTD", "Observed"),
        ]
        for index, fact in enumerate(facts):
            with cols[index % 4]:
                _profile_fact(*fact)
    with behavior_tab:
        cols = st.columns(4)
        frequency = player.sessions / max((ctx.end-ctx.start).days + 1, 1) * 30
        facts = [
            ("Casino GGR", money(player.casino_ggr, False), f"{int(player.sessions):,} sessions"),
            ("Sportsbook activity", f"{int(player.sports_bets):,} bets", f"{money(player.sports_handle, False)} handle"),
            ("Favorite game", str(player.favorite_game), "Most sessions, lifetime"),
            ("Session frequency", f"{frequency:.1f} / 30d", f"{player.minutes/max(player.sessions,1):.0f} avg minutes"),
            ("Last activity", f"{pd.Timestamp(player.last_activity):%d %b %Y, %H:%M}" if pd.notna(player.last_activity) else "No activity", "Observed"),
            ("RFM segment", str(player.rfm_segment), f"Recency {int(player.recency_days)} days"),
            ("Casino wagered", money(player.casino_bets, False), "Selected period"),
            ("Sportsbook GGR", money(player.sports_ggr, False), "Selected period"),
        ]
        for col, fact in zip(cols * 2, facts):
            with col:
                _profile_fact(*fact)
        preferred = favorite_games.run(ctx, selected)
        fig = px.bar(preferred, x="sessions", y="game_name", orientation="h", color="ggr", title="FAVORITE CASINO GAMES", color_continuous_scale=[COLORS["red"], COLORS["gold"], COLORS["green"]])
        chart(polish(fig, 320, False), preferred, explanation="Lifetime casino sessions ranked by game; color represents observed GGR.")
    with risk_tab:
        gauges = st.columns(5)
        for col, label, value in zip(gauges,
            ["Predicted churn 7D", "Predicted churn 14D", "Predicted churn 30D", "Predicted fraud", "Predicted RG risk"],
            [player.churn_probability_7d, player.churn_probability_14d, player.churn_probability_30d, player.fraud_risk, player.rg_risk]):
            with col:
                color = COLORS["red"] if value >= .55 else COLORS["gold"] if value >= .35 else COLORS["green"]
                fig = go.Figure(go.Indicator(mode="gauge+number", value=float(value)*100, number={"suffix": "%"}, gauge={"axis": {"range": [0, 100]}, "bar": {"color": color}, "steps": [{"range": [0,35], "color": "rgba(39,209,127,.10)"}, {"range": [35,55], "color": "rgba(245,184,75,.10)"}, {"range": [55,100], "color": "rgba(255,91,87,.10)"}]}, title={"text": label}))
                chart(polish(fig, 260, False), explanation="Model score; higher always means more risk.")
        rg_indicators = [
            ("RG review threshold", "Triggered" if player.rg_risk >= .55 else "Clear"),
            ("High session frequency", "Triggered" if frequency >= 20 else "Clear"),
            ("Long average sessions", "Triggered" if player.minutes/max(player.sessions,1) >= 75 else "Clear"),
            ("Marketing suppression", "Required" if player.rg_risk >= .55 else "Not required"),
        ]
        st.markdown("#### Responsible Gaming indicators")
        cols = st.columns(4)
        for col, fact in zip(cols, rg_indicators):
            with col:
                _profile_fact(fact[0], fact[1], "Decision-support indicator")
        st.info(f"Recommended action: {player.recommended_action}. Model confidence: {pct(player.model_confidence)}. Human review is required before intervention.")
    with timeline_tab:
        timeline = player_timeline.run(ctx, selected)
        timeline["event_date"] = pd.to_datetime(timeline.event_date)
        timeline["total_ggr"] = timeline.casino_ggr + timeline.sports_ggr
        fig = go.Figure()
        fig.add_trace(go.Bar(x=timeline.event_date, y=timeline.deposits, name="Deposits", marker_color=COLORS["green"]))
        fig.add_trace(go.Bar(x=timeline.event_date, y=-timeline.withdrawals, name="Withdrawals", marker_color=COLORS["gold"]))
        fig.add_trace(go.Scatter(x=timeline.event_date, y=timeline.total_ggr, name="GGR", line=dict(color=COLORS["cyan"], width=2.3), yaxis="y2"))
        fig.update_layout(title="PLAYER VALUE EVOLUTION", barmode="relative", yaxis2=dict(overlaying="y", side="right", showgrid=False, title="GGR"))
        chart(polish(fig, 390), timeline, explanation="Observed lifetime deposits, withdrawals and combined casino/sportsbook GGR by activity date.")
        data_table(timeline.tail(50).sort_values("event_date", ascending=False), column_config={"event_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"), "deposits": st.column_config.NumberColumn(format="$%.0f"), "withdrawals": st.column_config.NumberColumn(format="$%.0f"), "casino_ggr": st.column_config.NumberColumn(format="$%.0f"), "sports_ggr": st.column_config.NumberColumn(format="$%.0f")})
    with crm_tab:
        campaigns_received = _stable_number(selected, "campaigns", 0, 8)
        bonus_uses = _stable_number(selected, "bonus", 0, 5)
        st.warning("CRM campaign and bonus ledgers are not connected. The records below are deterministic demo simulations and are never included in observed KPIs.")
        cols = st.columns(3)
        with cols[0]: _profile_fact("Demo campaigns received", f"{campaigns_received}", "Simulated history")
        with cols[1]: _profile_fact("Demo bonus uses", f"{bonus_uses}", "Simulated history")
        with cols[2]: _profile_fact("Activation status", status, "Fraud + RG + KYC guardrail")
        demo_history = pd.DataFrame([
            {"date": (ctx.end - pd.Timedelta(14*(i+1), unit="D")).date(), "campaign": ["Retention journey", "Weekly value", "Game discovery", "VIP nurture"][i % 4], "channel": ["Email", "Push", "In-app"][i % 3], "status": ["Delivered", "Opened", "No response"][i % 3], "source_status": "Demo simulation"}
            for i in range(campaigns_received)
        ])
        data_table(demo_history, empty_title="No simulated campaign history for this player")
