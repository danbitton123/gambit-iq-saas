from __future__ import annotations

from hashlib import sha256

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from data.kpi_queries import OBSERVED_RETENTION_D30_SQL
from ui.charts import polish
from ui.components import chart, data_table, empty_state, kpis, money, pct, period_delta
from ui.theme import page_header


PLAYER_BASE_SQL = """
WITH casino AS (
  SELECT player_id,COUNT(*) sessions,SUM(duration_minutes) minutes,SUM(total_bet_amount) casino_bets,
         SUM(casino_ggr) casino_ggr,MAX(session_start) last_casino
  FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end GROUP BY player_id
), sports AS (
  SELECT player_id,COUNT(*) sports_bets,SUM(stake) sports_handle,SUM(sportsbook_ggr) sports_ggr,MAX(bet_date) last_sports
  FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end GROUP BY player_id
), payments AS (
  SELECT player_id,SUM(transaction_status='Approved' AND transaction_type='Deposit') deposit_count,
         SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END) deposits,
         SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END) withdrawals,
         MAX(transaction_date) last_payment
  FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end GROUP BY player_id
), lifetime AS (
  SELECT player_id,SUM(ggr) lifetime_ggr,MAX(activity_at) last_activity FROM (
    SELECT player_id,SUM(casino_ggr) ggr,MAX(session_start) activity_at FROM sessions GROUP BY player_id
    UNION ALL SELECT player_id,SUM(sportsbook_ggr),MAX(bet_date) FROM sports_bets GROUP BY player_id
  ) GROUP BY player_id
), ftd AS (
  SELECT player_id,MIN(transaction_date) ftd_date FROM transactions
  WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id
), favorite AS (
  SELECT player_id,game_name FROM (
    SELECT player_id,game_name,COUNT(*) uses,ROW_NUMBER() OVER(PARTITION BY player_id ORDER BY COUNT(*) DESC,game_name) rank
    FROM v_sessions_enriched GROUP BY player_id,game_name
  ) WHERE rank=1
)
SELECT v.player_id,v.country,v.channel,v.device,v.vip_level,v.kyc_status,v.registration_date,
       v.predicted_ltv_90d,v.churn_probability,v.fraud_risk,v.rg_risk,v.model_confidence,v.recommended_action,
       COALESCE(l.lifetime_ggr,0) lifetime_ggr,l.last_activity,f.ftd_date,COALESCE(c.sessions,0) sessions,
       COALESCE(c.minutes,0) minutes,COALESCE(c.casino_bets,0) casino_bets,COALESCE(c.casino_ggr,0) casino_ggr,
       COALESCE(s.sports_bets,0) sports_bets,COALESCE(s.sports_handle,0) sports_handle,COALESCE(s.sports_ggr,0) sports_ggr,
       COALESCE(t.deposit_count,0) deposit_count,COALESCE(t.deposits,0) deposits,COALESCE(t.withdrawals,0) withdrawals,
       COALESCE(fav.game_name,'No casino activity') favorite_game
FROM v_player_scores v LEFT JOIN casino c USING(player_id) LEFT JOIN sports s USING(player_id)
LEFT JOIN payments t USING(player_id) LEFT JOIN lifetime l USING(player_id) LEFT JOIN ftd f USING(player_id)
LEFT JOIN favorite fav USING(player_id) WHERE (:country='All markets' OR v.country=:country)
"""


SEGMENTS = [
    "All players", "VIP active", "VIP at risk", "New FTD", "Growing players",
    "Became inactive", "Potential bonus abuse", "RG risk", "High future value",
]


def _stable_number(player_id: str, salt: str, minimum: int, maximum: int) -> int:
    digest = sha256(f"{player_id}:{salt}".encode()).hexdigest()
    return minimum + int(digest[:8], 16) % (maximum - minimum + 1)


def _prepare_players(ctx) -> pd.DataFrame:
    players = ctx.query(PLAYER_BASE_SQL)
    previous = ctx.previous_query(PLAYER_BASE_SQL)[["player_id", "sessions", "sports_bets", "casino_ggr", "sports_ggr"]]
    previous = previous.rename(columns={column: f"previous_{column}" for column in previous.columns if column != "player_id"})
    players = players.merge(previous, on="player_id", how="left").fillna({
        "previous_sessions": 0, "previous_sports_bets": 0, "previous_casino_ggr": 0, "previous_sports_ggr": 0,
    })
    players["period_ggr"] = players.casino_ggr + players.sports_ggr
    players["previous_ggr"] = players.previous_casino_ggr + players.previous_sports_ggr
    players["activity"] = players.sessions + players.sports_bets
    players["previous_activity"] = players.previous_sessions + players.previous_sports_bets
    players["recency_days"] = (ctx.end.normalize() - pd.to_datetime(players.last_activity).dt.normalize()).dt.days.fillna(999).clip(lower=0)
    monetary_cutoff = max(float(players.loc[players.period_ggr > 0, "period_ggr"].quantile(.70) or 0), 1)
    frequency_cutoff = max(float(players.loc[players.activity > 0, "activity"].quantile(.70) or 0), 1)
    players["rfm_segment"] = "At risk"
    players.loc[(players.recency_days <= 30) & (players.activity > 0), "rfm_segment"] = "Active"
    players.loc[(players.recency_days <= 14) & (players.activity >= frequency_cutoff), "rfm_segment"] = "Loyal"
    players.loc[(players.recency_days <= 7) & (players.activity >= frequency_cutoff) & (players.period_ggr >= monetary_cutoff), "rfm_segment"] = "Champion"
    players.loc[(players.recency_days > 60), "rfm_segment"] = "Dormant"
    players["VIP active"] = players.vip_level.isin(["Gold", "Platinum"]) & (players.activity > 0)
    players["VIP at risk"] = players.vip_level.isin(["Gold", "Platinum"]) & (players.churn_probability >= .70)
    ftd_date = pd.to_datetime(players.ftd_date)
    players["New FTD"] = ftd_date.between(ctx.start, ctx.end + pd.Timedelta(1, unit="D"), inclusive="left")
    players["Growing players"] = (players.period_ggr > players.previous_ggr * 1.25) & (players.previous_ggr > 0)
    players["Became inactive"] = (players.activity == 0) & (players.previous_activity > 0)
    deposit_cutoff = max(float(players.deposit_count.quantile(.85) or 0), 2)
    players["Potential bonus abuse"] = (players.deposit_count >= deposit_cutoff) & players.fraud_risk.between(.35, .55, inclusive="left")
    players["RG risk"] = players.rg_risk >= .55
    players["High future value"] = players.predicted_ltv_90d >= 1800
    players["segment_tags"] = players.apply(lambda row: ", ".join(segment for segment in SEGMENTS[1:] if bool(row[segment])) or "Standard", axis=1)
    players["crm_eligible"] = (players.fraud_risk < .55) & (players.rg_risk < .55) & (players.kyc_status == "Verified")
    return players


def _profile_fact(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"<div class='player-fact'><span>{label}</span><strong>{value}</strong><small>{note}</small></div>",
        unsafe_allow_html=True,
    )


def render(ctx) -> None:
    page_header("PLAYER 360", "Complete player value, behavior, risk and activation intelligence", "Customer Intelligence")
    players = _prepare_players(ctx)
    if players.empty:
        empty_state("No players match this market")
        return

    active = players[players.activity > 0]
    previous_active = players[players.previous_activity > 0]
    retention = ctx.query(OBSERVED_RETENTION_D30_SQL).iloc[0]
    kpis([
        ("Observed Active Players", f"{len(active):,}", period_delta(len(active), len(previous_active))),
        ("Observed Lifetime GGR", money(players.lifetime_ggr.sum()), "All players in selected market"),
        ("Predicted LTV Proxy 90D", money(active.predicted_ltv_90d.sum()), "Active-player future value proxy"),
        ("Predicted High Churn Risk", f"{int((active.churn_probability >= .70).sum()):,}", "Active players ≥70%"),
        ("Predicted RG Interventions", f"{int(players['RG risk'].sum()):,}", "RG review threshold ≥55%"),
        ("Predicted VIP Candidates", f"{int(players['High future value'].sum()):,}", "LTV Proxy ≥ $1,800"),
        ("Observed Retention D30", pct(retention.retention_d30), f"{int(retention.retained_players or 0):,} / {int(retention.eligible_players or 0):,} eligible"),
    ], ctx)

    st.markdown("### Portfolio segmentation")
    segment_counts = pd.DataFrame({"segment": SEGMENTS[1:], "players": [int(players[name].sum()) for name in SEGMENTS[1:]]})
    segment_cols = st.columns(4)
    for index, row in enumerate(segment_counts.itertuples()):
        with segment_cols[index % 4]:
            st.markdown(f"<div class='segment-tile'><span>{row.segment}</span><strong>{row.players:,}</strong><small>Players · segments may overlap</small></div>", unsafe_allow_html=True)

    f1, f2 = st.columns([1.1, 1])
    with f1:
        segment_choice = st.selectbox("Business segment", SEGMENTS, key="player_360_segment")
    with f2:
        crm_safe = st.toggle("CRM-safe export only", value=True, help="Excludes fraud/RG review cases and players without verified KYC.")
    filtered = players if segment_choice == "All players" else players[players[segment_choice]]
    export = filtered[filtered.crm_eligible] if crm_safe else filtered
    export_columns = ["player_id", "country", "vip_level", "rfm_segment", "segment_tags", "lifetime_ggr", "predicted_ltv_90d", "churn_probability", "recommended_action", "model_confidence"]
    st.download_button(
        f"Export {len(export):,} players to CSV", export[export_columns].to_csv(index=False).encode("utf-8"),
        file_name=f"gambit_iq_{segment_choice.lower().replace(' ', '_')}_crm.csv", mime="text/csv",
        disabled=export.empty, help="Simulated CRM activation list. No campaign is sent automatically.",
    )
    st.caption(f"{len(filtered):,} players in segment · {len(export):,} eligible for the current export guardrail.")
    if filtered.empty:
        empty_state("No players match this business segment")
        return

    st.markdown("### Individual player record")
    selected = st.selectbox("Search anonymized player ID", filtered.player_id.tolist(), key="player_360_selected")
    player = players.loc[players.player_id == selected].iloc[0]
    status = "CRM eligible" if player.crm_eligible else "Suppressed from CRM"
    st.markdown(
        f"<section class='player-identity'><div><span>ANONYMIZED PLAYER</span><h3>{selected}</h3>"
        f"<p>{player.country} · {player.vip_level} · {player.rfm_segment} · {player.channel} · {player.device}</p></div>"
        f"<strong class={'identity-good' if player.crm_eligible else 'identity-risk'}>{status}</strong></section>", unsafe_allow_html=True,
    )

    value_tab, behavior_tab, risk_tab, timeline_tab, crm_tab = st.tabs(["Value & cash", "Gaming behavior", "Risk & RG", "Timeline", "CRM history"])
    with value_tab:
        cols = st.columns(4)
        facts = [
            ("Observed lifetime GGR", money(player.lifetime_ggr, False), "Casino + sportsbook"),
            ("Predicted LTV Proxy 90D", money(player.predicted_ltv_90d, False), "Predicted positive GGR proxy"),
            ("Observed deposits", money(player.deposits, False), f"{int(player.deposit_count):,} approved deposits"),
            ("Observed withdrawals", money(player.withdrawals, False), "Approved transactions"),
            ("Observed period GGR", money(player.period_ggr, False), ctx.period_label),
            ("Observed net cash flow", money(player.deposits-player.withdrawals, False), "Deposits − withdrawals"),
            ("Estimated bonus provision", money(max(player.period_ggr, 0)*.065, False), "Demo assumption: 6.5% of positive GGR"),
            ("First approved deposit", f"{pd.Timestamp(player.ftd_date):%d %b %Y}" if pd.notna(player.ftd_date) else "No FTD", "Observed"),
        ]
        for col, fact in zip(cols * 2, facts):
            with col:
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
        preferred = ctx.query("""SELECT game_name,COUNT(*) sessions,SUM(total_bet_amount) bets,SUM(casino_ggr) ggr
          FROM v_sessions_enriched WHERE player_id=:player_id GROUP BY game_name ORDER BY sessions DESC LIMIT 5""", {"player_id": selected})
        fig = px.bar(preferred, x="sessions", y="game_name", orientation="h", color="ggr", title="FAVORITE CASINO GAMES", color_continuous_scale=[COLORS["red"], COLORS["gold"], COLORS["green"]])
        chart(polish(fig, 320, False), preferred, explanation="Lifetime casino sessions ranked by game; color represents observed GGR.")
    with risk_tab:
        gauges = st.columns(3)
        for col, label, value in zip(gauges, ["Predicted churn", "Predicted fraud", "Predicted RG risk"], [player.churn_probability, player.fraud_risk, player.rg_risk]):
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
        timeline = ctx.query("""SELECT event_date,SUM(deposits) deposits,SUM(withdrawals) withdrawals,SUM(casino_ggr) casino_ggr,SUM(sports_ggr) sports_ggr,SUM(events) events FROM (
          SELECT DATE(session_start) event_date,0 deposits,0 withdrawals,SUM(casino_ggr) casino_ggr,0 sports_ggr,COUNT(*) events FROM sessions WHERE player_id=:player_id GROUP BY DATE(session_start)
          UNION ALL SELECT DATE(bet_date),0,0,0,SUM(sportsbook_ggr),COUNT(*) FROM sports_bets WHERE player_id=:player_id GROUP BY DATE(bet_date)
          UNION ALL SELECT DATE(transaction_date),SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END),SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END),0,0,COUNT(*) FROM transactions WHERE player_id=:player_id GROUP BY DATE(transaction_date)
        ) GROUP BY event_date ORDER BY event_date""", {"player_id": selected})
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

    st.markdown("### Player portfolio")
    portfolio = filtered[["player_id", "country", "vip_level", "rfm_segment", "segment_tags", "lifetime_ggr", "predicted_ltv_90d", "churn_probability", "fraud_risk", "rg_risk", "recommended_action"]].sort_values(["rg_risk", "churn_probability", "predicted_ltv_90d"], ascending=[False, False, False]).head(250)
    data_table(portfolio, column_config={
        "lifetime_ggr": st.column_config.NumberColumn("Observed lifetime GGR", format="$%.0f"),
        "predicted_ltv_90d": st.column_config.NumberColumn("Predicted LTV Proxy 90D", format="$%.0f"),
        "churn_probability": st.column_config.ProgressColumn("Predicted churn", min_value=0, max_value=1, format="%.1%%"),
        "fraud_risk": st.column_config.ProgressColumn("Predicted fraud", min_value=0, max_value=1, format="%.1%%"),
        "rg_risk": st.column_config.ProgressColumn("Predicted RG", min_value=0, max_value=1, format="%.1%%"),
    })
