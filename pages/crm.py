from __future__ import annotations
import plotly.express as px
import streamlit as st
from config import COLORS
from data.decision_engine import DecisionEngine
from queries.crm import experiment_scenario, metrics, next_best_action_queue, segments
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money,team_alert_block
from ui.theme import page_header

TEAM = {"VIP & CRM"}

def render(ctx)->None:
    page_header("PLAYER ACTIVATION STUDIO","Segments, journeys and next best action","CRM Automation")
    m=metrics.run(ctx)
    kpis([("Predicted Targetable Players",f"{int(m.targetable):,}","Active and safety-filtered"),("Estimated Campaign Opportunity",money(m.revenue),"8% of predicted LTV proxy 90D"),("Estimated Uplift Assumption","+23.6%","Not an observed experiment"),("Predicted Risk Suppressions",f"{int(m.suppressed):,}","Fraud or RG score ≥55%")],ctx)
    st.caption("Observed Bonus Efficiency is not shown — it requires connected bonus-cost data that isn't available yet.")
    segment_rows=segments.run(ctx)
    if int(segment_rows.Players.sum()) == 0:
        empty_state("No CRM segments match these filters")
        return
    left,middle,right=st.columns([1,1.7,1.4],gap="medium")
    with left:
        st.markdown("#### Dynamic SQL segments")
        for row in segment_rows.itertuples(): insight(row.Segment,f"{row.Players:,} players","View segment")
    with middle:
        st.markdown("#### Journey governance flow");st.graphviz_chart('digraph G { rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fillcolor="#0a2730" color="#27d17f" fontcolor="white"]; a[label="TRIGGER"]; b[label="SAFETY CHECK"]; c[label="SEGMENT"]; d[label="CHANNEL"]; e[label="CONTROL"]; f[label="MEASURE"]; a->b->c->d->e->f; }',width="stretch");st.caption("Required control flow for every CRM activation; this diagram describes governance and is not a live campaign builder.")
    with right:
        queue=next_best_action_queue.run(ctx);st.markdown("#### Next best action");data_table(queue,column_config={"predicted_ltv_90d":st.column_config.NumberColumn("Predicted remaining LTV 90D",format="$%.0f"),"model_confidence":st.column_config.ProgressColumn("Predicted confidence",min_value=0,max_value=1,format="%.1%%")})

    st.markdown("### VIP & CRM alerts")
    with st.spinner("Evaluating governed decision rules…"):
        alerts = DecisionEngine(ctx).evaluate()
    team_alert_block(alerts, TEAM, empty_message="No revenue-concentration threshold is currently breached for this scope.")

    exp=experiment_scenario.run(ctx, m.revenue)
    c1,c2=st.columns([2,1],gap="medium")
    with c1:
        fig=px.bar(exp,x="Variant",y="revenue",color="Variant",text="uplift",title="DEMO SCENARIO · NOT OBSERVED",color_discrete_sequence=["#556b7a",COLORS["cyan"],COLORS["green"]]);fig.update_traces(texttemplate="%{text:.1%}");chart(polish(fig,340,False),exp,explanation="Scenario based on explicit uplift assumptions; replace with controlled-experiment results when real campaign data is connected.")
    with c2: chart(polish(px.funnel(segment_rows,x="Players",y="Segment",title="SEGMENT SIZES"),340,False),segment_rows,explanation="Segments may overlap and therefore do not represent sequential funnel conversion.")
