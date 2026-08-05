from __future__ import annotations
import plotly.express as px
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import insight,kpis,money
from ui.theme import page_header

def render(ctx)->None:
    page_header("TRUST & RISK CENTER","Fraud, AML, KYC and player protection","Risk & Compliance")
    m=ctx.query("""SELECT COUNT(*) accounts,SUM(fraud_risk>=.55 OR rg_risk>=.55) cases,SUM(CASE WHEN fraud_risk>=.55 THEN MAX(lifetime_ggr,0) ELSE 0 END) prevented,SUM(rg_risk>=.55) rg,SUM(fraud_risk>=.55) fraud FROM v_player_scores WHERE (:country='All markets' OR country=:country)""").iloc[0]
    kpis([("Accounts Monitored",f"{int(m.accounts):,}","ML scoring coverage"),("High-Risk Cases",f"{int(m.cases):,}","Fraud or RG threshold"),("Fraud Loss Prevented",money(m.prevented),"Estimated exposure"),("AML Reviews",f"{int(m.cases*.69):,}","Review workload"),("RG Interventions",f"{int(m.rg):,}","Player protection")])
    series=ctx.query("""SELECT DATE(last_session) date,'Fraud' Risk,AVG(fraud_risk)*100 Score FROM v_player_scores WHERE (:country='All markets' OR country=:country) GROUP BY date UNION ALL SELECT DATE(last_session),'Responsible gaming',AVG(rg_risk)*100 FROM v_player_scores WHERE (:country='All markets' OR country=:country) GROUP BY DATE(last_session) UNION ALL SELECT DATE(last_session),'Churn',AVG(churn_probability)*100 FROM v_player_scores WHERE (:country='All markets' OR country=:country) GROUP BY DATE(last_session) ORDER BY date""")
    left,right=st.columns([3.1,1])
    with left: st.plotly_chart(polish(px.line(series,x="date",y="Score",color="Risk",title="RISK MONITORING · ML SCORES"),390),width="stretch")
    with right: st.markdown("<p class='panel-title'>Critical alerts</p>",unsafe_allow_html=True);insight("Multi-account review","Device and payment links require investigation.","HIGH",True);insight("Elevated harm indicators","Behavioral risk score increased.","Immediate review",True)
    cases=ctx.query("""SELECT player_id,CASE WHEN rg_risk>=fraud_risk THEN 'Player protection' ELSE 'Fraud / AML' END trigger,CASE WHEN MAX(fraud_risk,rg_risk)>=.75 THEN 'Critical' WHEN MAX(fraud_risk,rg_risk)>=.55 THEN 'High' ELSE 'Medium' END severity,model_confidence,recommended_action,CASE ABS(RANDOM())%3 WHEN 0 THEN 'Open' WHEN 1 THEN 'In review' ELSE 'Pending info' END status,fraud_risk,rg_risk,predicted_ltv_90d,MAX(fraud_risk,rg_risk) risk_score FROM v_player_scores WHERE (fraud_risk>=.40 OR rg_risk>=.40) AND (:country='All markets' OR country=:country) ORDER BY risk_score DESC LIMIT 120""");st.markdown("#### Case-management queue");st.dataframe(cases[["player_id","trigger","severity","model_confidence","recommended_action","status"]].head(80),width="stretch",hide_index=True)
    actions=ctx.query("""SELECT 'Manual review' action,COUNT(*) Cases FROM v_player_scores WHERE (fraud_risk>=.55 OR rg_risk>=.55) AND (:country='All markets' OR country=:country) UNION ALL SELECT 'Cooling-off reminder',COUNT(*) FROM v_player_scores WHERE rg_risk>=.55 AND (:country='All markets' OR country=:country) UNION ALL SELECT 'Marketing suppression',COUNT(*) FROM v_player_scores WHERE rg_risk>=.40 AND (:country='All markets' OR country=:country) UNION ALL SELECT 'Source-of-funds request',COUNT(*) FROM v_player_scores WHERE fraud_risk>=.55 AND (:country='All markets' OR country=:country)""")
    c1,c2=st.columns([1.45,1])
    with c1: st.plotly_chart(polish(px.scatter(cases,x="fraud_risk",y="rg_risk",size="predicted_ltv_90d",color="severity",hover_name="player_id",title="PLAYER RISK CLUSTERS",color_discrete_map={"Medium":COLORS["gold"],"High":COLORS["red"],"Critical":"#c92d44"}),370),width="stretch")
    with c2: st.plotly_chart(polish(px.bar(actions,x="Cases",y="action",orientation="h",title="PLAYER PROTECTION ACTIONS",color="Cases",color_continuous_scale=[COLORS["green"],COLORS["gold"],COLORS["red"]]),370,False),width="stretch")
