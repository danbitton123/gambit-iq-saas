from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from data.kpi_queries import OBSERVED_RETENTION_D30_SQL
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight, kpis, money, pct, period_delta
from ui.theme import page_header


def render(ctx) -> None:
    page_header("PLAYER 360 & INTELLIGENCE", "Lifecycle, value, churn and player-level decisions", "Player Intelligence")
    metric_sql = """WITH activity AS (SELECT player_id FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) UNION SELECT player_id FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country)), active AS (SELECT v.player_id,v.predicted_ltv_90d,v.churn_probability FROM activity a JOIN v_player_scores v USING(player_id)) SELECT COUNT(*) active,AVG(predicted_ltv_90d) avg_ltv,SUM(churn_probability>=.70) high_churn,SUM(predicted_ltv_90d>=1800) vip FROM active"""
    m = ctx.query(metric_sql).iloc[0]
    previous = ctx.previous_query(metric_sql).iloc[0]
    retention=ctx.query(OBSERVED_RETENTION_D30_SQL).iloc[0]
    kpis([("Observed Active Players", f"{int(m.active or 0):,}", period_delta(m.active, previous.active)),("Predicted LTV Proxy 90D", money(m.avg_ltv,False), "ML GGR proxy for active players"),("Predicted High Churn Risk", f"{int(m.high_churn or 0):,}", "≥70% predicted probability"),("Predicted VIP Candidates", f"{int(m.vip or 0):,}", "LTV proxy ≥ $1,800"),("Observed Retention D30", pct(retention.retention_d30), f"{int(retention.retained_players or 0):,} / {int(retention.eligible_players or 0):,} eligible")],ctx)
    players = ctx.query("""SELECT v.player_id,v.vip_level,v.country,v.predicted_ltv_90d,v.churn_probability,v.fraud_risk,v.rg_risk,v.recommended_action,v.model_confidence
      FROM v_player_scores v
      WHERE (:country='All markets' OR v.country=:country) AND (EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end) OR EXISTS (SELECT 1 FROM v_sports_bets_enriched b WHERE b.player_id=v.player_id AND b.bet_date>=:start AND b.bet_date<:end))
      ORDER BY CASE WHEN v.recommended_action<>'Monitor' THEN 0 ELSE 1 END,v.rg_risk DESC,v.fraud_risk DESC,v.predicted_ltv_90d DESC""")
    if players.empty:
        empty_state("No active players match these filters")
        return
    selected=st.selectbox("Search an anonymized player",players.player_id.tolist()); p=players.loc[players.player_id==selected].iloc[0]
    st.markdown(f"### {selected} · {p.vip_level} · {p.country}")
    kpis([("Predicted LTV Proxy 90D",money(p.predicted_ltv_90d,False),"Selected player"),("Predicted Churn Probability",pct(p.churn_probability),"Selected player"),("Predicted Fraud Risk",pct(p.fraud_risk),"Review proxy"),("Predicted RG Risk",pct(p.rg_risk),"Review proxy"),("Predicted Model Confidence Detail",pct(p.model_confidence),"Selected player")],ctx)
    recent=ctx.query("""SELECT session_start,game_name,duration_minutes,total_bet_amount,casino_ggr FROM v_sessions_enriched WHERE player_id=:player_id ORDER BY session_start DESC LIMIT 8""",{"player_id":selected})
    l,r=st.columns([2.8,1])
    with l:
        st.markdown("#### Recent activity")
        data_table(recent, column_config={"session_start": st.column_config.DatetimeColumn("Session", format="DD MMM YYYY, HH:mm"), "total_bet_amount": st.column_config.NumberColumn("Bets", format="$%.2f"), "casino_ggr": st.column_config.NumberColumn("GGR", format="$%.2f"), "duration_minutes": st.column_config.NumberColumn("Minutes", format="%.0f")})
    with r:
        st.markdown("#### AI recommendation"); blocked=p.rg_risk>=.55 or p.fraud_risk>=.55
        insight(str(p.recommended_action),"Commercial campaigns suppressed; manual review required." if blocked else "Owner approval and control-group measurement required.",f"Confidence {pct(p.model_confidence)}",blocked)
    c1,c2,c3=st.columns(3)
    with c1:
        cohort=ctx.query("""WITH activity AS (SELECT p.player_id,strftime('%Y-%m',p.registration_date) cohort,
          MIN(6,MAX(0,(CAST(strftime('%Y',s.session_start) AS INT)-CAST(strftime('%Y',p.registration_date) AS INT))*12+CAST(strftime('%m',s.session_start) AS INT)-CAST(strftime('%m',p.registration_date) AS INT))) month_n
          FROM players p JOIN v_sessions_enriched s ON s.player_id=p.player_id WHERE s.session_start>=p.registration_date
            AND s.session_start>=:start AND s.session_start<:end AND (:country='All markets' OR p.country=:country)),
          counts AS (SELECT cohort,month_n,COUNT(DISTINCT player_id) players FROM activity GROUP BY cohort,month_n), base AS (SELECT cohort,players base FROM counts WHERE month_n=0)
          SELECT c.cohort,c.month_n,1.0*c.players/NULLIF(b.base,0) retention FROM counts c JOIN base b USING(cohort) ORDER BY cohort,c.month_n""")
        matrix=cohort.pivot(index="cohort",columns="month_n",values="retention").tail(7)
        fig=px.imshow(matrix,text_auto=".0%",aspect="auto",title="MONTHLY COHORT ACTIVITY · SQL",color_continuous_scale=["#14252c",COLORS["green"]]);fig.update_layout(coloraxis_showscale=False);chart(polish(fig,360,False), cohort, explanation="Share of each registration cohort active in each observed month. The official Observed Retention D30 KPI uses the separate days 30–36 definition shown above.")
    with c2:
        sample=players[["player_id","churn_probability","predicted_ltv_90d","vip_level"]].head(1800)
        chart(polish(px.scatter(sample,x="churn_probability",y="predicted_ltv_90d",color="vip_level",title="LTV PROXY VS CHURN · ML SCORES",color_discrete_sequence=[COLORS["cyan"],COLORS["green"],COLORS["gold"],COLORS["red"]]),360), sample, explanation="Predictions are shown only for players active inside the global filters. Value is a 90-day GGR proxy, not true net LTV.")
    with c3:
        chart(polish(px.histogram(players,x="predicted_ltv_90d",nbins=35,title="PREDICTED LTV PROXY 90D DISTRIBUTION",color_discrete_sequence=[COLORS["cyan"]]),360,False), players, explanation="Distribution of the modelled 90-day GGR proxy for active players; this is not observed NGR or true lifetime value.")
    st.markdown("#### Players requiring attention")
    attention=players[players.recommended_action!="Monitor"].head(100)
    data_table(attention, column_config={"predicted_ltv_90d": st.column_config.NumberColumn("Predicted LTV proxy 90D", format="$%.0f"), "churn_probability": st.column_config.ProgressColumn("Predicted churn", min_value=0, max_value=1, format="%.1%%"), "fraud_risk": st.column_config.ProgressColumn("Predicted fraud risk", min_value=0, max_value=1, format="%.1%%"), "rg_risk": st.column_config.ProgressColumn("Predicted RG risk", min_value=0, max_value=1, format="%.1%%"), "model_confidence": st.column_config.ProgressColumn("Model confidence", min_value=0, max_value=1, format="%.1%%")})
