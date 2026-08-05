from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from ui.charts import polish
from ui.components import insight, kpis, money, pct
from ui.theme import page_header


def render(ctx) -> None:
    page_header("PLAYER 360 & INTELLIGENCE", "Lifecycle, value, churn and player-level decisions", "Player Intelligence")
    m = ctx.query("""SELECT COUNT(DISTINCT s.player_id) active,AVG(v.predicted_ltv_90d) avg_ltv,
        SUM(CASE WHEN v.churn_probability>=.70 THEN 1 ELSE 0 END) high_churn,
        SUM(CASE WHEN v.predicted_ltv_90d>=1800 THEN 1 ELSE 0 END) vip,
        1-AVG(v.churn_probability) retained
      FROM v_sessions_enriched s JOIN v_player_scores v ON v.player_id=s.player_id
      WHERE s.session_start>=:start AND s.session_start<:end AND (:country='All markets' OR s.country=:country)""").iloc[0]
    kpis([("Active Players", f"{int(m.active):,}", "SQL distinct players"),("Predicted 90D LTV", money(m.avg_ltv,False), "Python ML score"),("High Churn Risk", f"{int(m.high_churn):,}", "Review priority"),("VIP Candidates", f"{int(m.vip):,}", "ML opportunity"),("Modelled Retention", pct(m.retained), "1 − mean churn")])
    players = ctx.query("""SELECT DISTINCT v.player_id,v.vip_level,v.country,v.predicted_ltv_90d,v.churn_probability,v.fraud_risk,v.rg_risk,v.recommended_action,v.model_confidence
      FROM v_player_scores v JOIN v_sessions_enriched s ON s.player_id=v.player_id
      WHERE s.session_start>=:start AND s.session_start<:end AND (:country='All markets' OR s.country=:country)
      ORDER BY CASE WHEN v.recommended_action<>'Monitor' THEN 0 ELSE 1 END,v.rg_risk DESC,v.fraud_risk DESC,v.predicted_ltv_90d DESC""")
    selected=st.selectbox("Search an anonymized player",players.player_id.tolist()); p=players.loc[players.player_id==selected].iloc[0]
    st.markdown(f"### {selected} · {p.vip_level} · {p.country}")
    cols=st.columns(5)
    for col,(label,value) in zip(cols,[("Predicted LTV",money(p.predicted_ltv_90d,False)),("Churn probability",pct(p.churn_probability)),("Fraud risk",pct(p.fraud_risk)),("RG risk",pct(p.rg_risk)),("Model confidence",pct(p.model_confidence))]): col.metric(label,value)
    recent=ctx.query("""SELECT session_start,game_name,duration_minutes,total_bet_amount,casino_ggr FROM v_sessions_enriched WHERE player_id=:player_id ORDER BY session_start DESC LIMIT 8""",{"player_id":selected})
    l,r=st.columns([2.8,1])
    with l: st.markdown("#### Recent activity"); st.dataframe(recent,width="stretch",hide_index=True)
    with r:
        st.markdown("#### AI recommendation"); blocked=p.rg_risk>=.55 or p.fraud_risk>=.55
        insight(str(p.recommended_action),"Commercial campaigns suppressed; manual review required." if blocked else "Owner approval and control-group measurement required.",f"Confidence {pct(p.model_confidence)}",blocked)
    c1,c2,c3=st.columns(3)
    with c1:
        cohort=ctx.query("""WITH activity AS (SELECT p.player_id,strftime('%Y-%m',p.registration_date) cohort,
          MIN(6,MAX(0,(CAST(strftime('%Y',s.session_start) AS INT)-CAST(strftime('%Y',p.registration_date) AS INT))*12+CAST(strftime('%m',s.session_start) AS INT)-CAST(strftime('%m',p.registration_date) AS INT))) month_n
          FROM players p JOIN v_sessions_enriched s ON s.player_id=p.player_id WHERE s.session_start>=p.registration_date AND (:country='All markets' OR p.country=:country)),
          counts AS (SELECT cohort,month_n,COUNT(DISTINCT player_id) players FROM activity GROUP BY cohort,month_n), base AS (SELECT cohort,players base FROM counts WHERE month_n=0)
          SELECT c.cohort,c.month_n,1.0*c.players/NULLIF(b.base,0) retention FROM counts c JOIN base b USING(cohort) ORDER BY cohort,c.month_n""")
        matrix=cohort.pivot(index="cohort",columns="month_n",values="retention").tail(7)
        fig=px.imshow(matrix,text_auto=".0%",aspect="auto",title="COHORT RETENTION · SQL",color_continuous_scale=["#14252c",COLORS["green"]]);fig.update_layout(coloraxis_showscale=False);st.plotly_chart(polish(fig,360,False),width="stretch")
    with c2:
        sample=ctx.query("""SELECT player_id,churn_probability,predicted_ltv_90d,vip_level FROM v_player_scores WHERE (:country='All markets' OR country=:country) ORDER BY RANDOM() LIMIT 1800""")
        st.plotly_chart(polish(px.scatter(sample,x="churn_probability",y="predicted_ltv_90d",color="vip_level",title="VALUE VS CHURN · ML SCORES",color_discrete_sequence=[COLORS["cyan"],COLORS["green"],COLORS["gold"],COLORS["red"]]),360),width="stretch")
    with c3:
        st.plotly_chart(polish(px.histogram(players,x="predicted_ltv_90d",nbins=35,title="PREDICTED 90D LTV DISTRIBUTION",color_discrete_sequence=[COLORS["cyan"]]),360,False),width="stretch")
    st.markdown("#### Players requiring attention")
    st.dataframe(players[players.recommended_action!="Monitor"].head(100),width="stretch",hide_index=True)
