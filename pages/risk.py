from __future__ import annotations
import plotly.express as px
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money
from ui.theme import page_header

def render(ctx)->None:
    page_header("TRUST & RISK CENTER","Fraud, AML, KYC and player protection","Risk & Compliance")
    active="""(:country='All markets' OR v.country=:country) AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end)"""
    m=ctx.query(f"""SELECT COUNT(*) accounts,SUM(fraud_risk>=.55 OR rg_risk>=.55) cases,SUM(CASE WHEN fraud_risk>=.55 THEN MAX(lifetime_ggr,0) ELSE 0 END) exposure,SUM(rg_risk>=.55) rg,SUM(fraud_risk>=.55) fraud FROM v_player_scores v WHERE {active}""").iloc[0]
    kpis([("Active Accounts Scored",f"{int(m.accounts or 0):,}","Players active in filter"),("High-Risk Cases",f"{int(m.cases or 0):,}","Fraud or RG score ≥55%"),("Estimated Fraud Exposure",money(m.exposure),"Lifetime GGR proxy; not prevented loss"),("Fraud Reviews",f"{int(m.fraud or 0):,}","Manual review workload"),("RG Interventions",f"{int(m.rg or 0):,}","Player-protection queue")])
    series=ctx.query("""SELECT DATE(last_session) date,'Fraud' Risk,AVG(fraud_risk)*100 Score FROM v_player_scores v WHERE last_session>=:start AND last_session<:end AND (:country='All markets' OR v.country=:country) GROUP BY date UNION ALL SELECT DATE(last_session),'Responsible gaming',AVG(rg_risk)*100 FROM v_player_scores v WHERE last_session>=:start AND last_session<:end AND (:country='All markets' OR v.country=:country) GROUP BY DATE(last_session) UNION ALL SELECT DATE(last_session),'Churn',AVG(churn_probability)*100 FROM v_player_scores v WHERE last_session>=:start AND last_session<:end AND (:country='All markets' OR v.country=:country) GROUP BY DATE(last_session) ORDER BY date""")
    if series.empty:
        empty_state("No scored player activity matches these filters")
        return
    left,right=st.columns([3.1,1])
    with left: chart(polish(px.line(series,x="date",y="Score",color="Risk",title="RISK MONITORING · ML SCORES"),390),series,explanation="Average model scores by players' last observed session date; higher values always indicate higher risk.")
    with right: st.markdown("<p class='panel-title'>Filtered alerts</p>",unsafe_allow_html=True);insight("Fraud review queue","Active accounts above the fraud threshold.",f"{int(m.fraud or 0):,} reviews",True);insight("Player protection queue","Active accounts above the RG threshold.",f"{int(m.rg or 0):,} interventions",True)
    cases=ctx.query(f"""SELECT player_id,CASE WHEN rg_risk>=fraud_risk THEN 'Player protection' ELSE 'Fraud / AML' END trigger,CASE WHEN MAX(fraud_risk,rg_risk)>=.75 THEN 'Critical' WHEN MAX(fraud_risk,rg_risk)>=.55 THEN 'High' ELSE 'Medium' END severity,model_confidence,recommended_action,CASE CAST(SUBSTR(player_id,-1) AS INTEGER)%3 WHEN 0 THEN 'Open' WHEN 1 THEN 'In review' ELSE 'Pending info' END status,fraud_risk,rg_risk,predicted_ltv_90d,MAX(fraud_risk,rg_risk) risk_score FROM v_player_scores v WHERE (fraud_risk>=.40 OR rg_risk>=.40) AND {active} ORDER BY risk_score DESC LIMIT 120""");st.markdown("#### Case-management queue");data_table(cases[["player_id","trigger","severity","model_confidence","recommended_action","status"]].head(80),column_config={"model_confidence":st.column_config.ProgressColumn("Confidence",min_value=0,max_value=1,format="%.1%%")})
    actions=ctx.query(f"""SELECT 'Manual review' action,COUNT(*) Cases FROM v_player_scores v WHERE (fraud_risk>=.55 OR rg_risk>=.55) AND {active} UNION ALL SELECT 'Cooling-off reminder',COUNT(*) FROM v_player_scores v WHERE rg_risk>=.55 AND {active} UNION ALL SELECT 'Marketing suppression',COUNT(*) FROM v_player_scores v WHERE rg_risk>=.40 AND {active} UNION ALL SELECT 'Source-of-funds request',COUNT(*) FROM v_player_scores v WHERE fraud_risk>=.55 AND {active}""")
    c1,c2=st.columns([1.45,1])
    with c1: chart(polish(px.scatter(cases,x="fraud_risk",y="rg_risk",size="predicted_ltv_90d",color="severity",hover_name="player_id",title="PLAYER RISK CLUSTERS",color_discrete_map={"Medium":COLORS["gold"],"High":COLORS["red"],"Critical":"#c92d44"}),370),cases,explanation="Green is never used for flagged cases; amber, red and dark red indicate increasing severity.")
    with c2: chart(polish(px.bar(actions,x="Cases",y="action",orientation="h",title="PLAYER PROTECTION ACTIONS",color="Cases",color_continuous_scale=[COLORS["gold"],COLORS["red"]]),370,False),actions,explanation="Required review actions derived from filtered risk thresholds.")
