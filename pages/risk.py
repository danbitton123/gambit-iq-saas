from __future__ import annotations
import plotly.express as px
import streamlit as st
from config import COLORS
from data.decision_engine import DecisionEngine
from queries.risk import case_queue, metrics, protection_actions, risk_trend
from ui.charts import polish
from ui.components import chart, data_table, empty_state, kpis, money, team_alert_block
from ui.theme import page_header

TEAM = {"Risk & Compliance", "Player Protection"}

def render(ctx)->None:
    page_header("TRUST & RISK CENTER","Fraud, AML, KYC and player protection","Risk & Compliance")
    m=metrics.run(ctx)
    kpis([("Predicted Active Accounts Scored",f"{int(m.accounts or 0):,}","Players active in filter"),("Predicted High-Risk Cases",f"{int(m.cases or 0):,}","Fraud or RG score ≥55%"),("Estimated Fraud Exposure",money(m.exposure),"Lifetime GGR proxy; not prevented loss"),("Predicted Fraud Reviews",f"{int(m.fraud or 0):,}","Manual review workload"),("Predicted RG Interventions",f"{int(m.rg or 0):,}","Player-protection queue")],ctx)
    series=risk_trend.run(ctx)
    if series.empty:
        empty_state("No scored player activity matches these filters")
        return
    chart(polish(px.line(series,x="date",y="Score",color="Risk",title="RISK MONITORING · ML SCORES"),330),series,explanation="Average model scores by players' last observed session date; higher values always indicate higher risk.")

    st.markdown("### Risk & Compliance / Player Protection alerts")
    with st.spinner("Evaluating governed decision rules…"):
        alerts = DecisionEngine(ctx).evaluate()
    # Same population as the KPI row above (queries/risk/active_condition.py's ACTIVE_CONDITION
    # matches DecisionEngine._player_risk()'s casino+sportsbook activity predicate exactly), so
    # this page's numbers can never quietly diverge from the same alerts on Command Center / AI Copilot.
    team_alert_block(alerts, TEAM, empty_message="No fraud or RG case is currently above the review threshold for this scope.")

    cases=case_queue.run(ctx);st.markdown("#### Case-management queue");data_table(cases[["player_id","trigger","severity","model_confidence","recommended_action","status"]].head(80),column_config={"model_confidence":st.column_config.ProgressColumn("Confidence",min_value=0,max_value=1,format="%.1%%")})
    actions=protection_actions.run(ctx)
    c1,c2=st.columns([1.45,1],gap="medium")
    with c1: chart(polish(px.scatter(cases,x="fraud_risk",y="rg_risk",size="predicted_ltv_90d",color="severity",hover_name="player_id",title="PLAYER RISK CLUSTERS",color_discrete_map={"Medium":COLORS["gold"],"High":COLORS["red"],"Critical":"#c92d44"}),370),cases,explanation="Green is never used for flagged cases; amber, red and dark red indicate increasing severity.")
    with c2: chart(polish(px.bar(actions,x="Cases",y="action",orientation="h",title="PLAYER PROTECTION ACTIONS",color="Cases",color_continuous_scale=[COLORS["gold"],COLORS["red"]]),370,False),actions,explanation="Required review actions derived from filtered risk thresholds.")
