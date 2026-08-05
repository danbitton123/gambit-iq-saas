from __future__ import annotations
import plotly.express as px
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money
from ui.theme import page_header

def render(ctx)->None:
    page_header("PLAYER ACTIVATION STUDIO","Segments, journeys and next best action","CRM Automation")
    active="""(:country='All markets' OR v.country=:country) AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end)"""
    m=ctx.query(f"""SELECT COALESCE(SUM(fraud_risk<.55 AND rg_risk<.55),0) targetable,COALESCE(SUM(NOT(fraud_risk<.55 AND rg_risk<.55)),0) suppressed,COALESCE(SUM(CASE WHEN fraud_risk<.55 AND rg_risk<.55 AND recommended_action IN ('Retention review','VIP review') THEN predicted_ltv_90d*.08 ELSE 0 END),0) revenue FROM v_player_scores v WHERE {active}""").iloc[0]
    kpis([("Predicted Targetable Players",f"{int(m.targetable):,}","Active and safety-filtered"),("Estimated Campaign Opportunity",money(m.revenue),"8% of predicted LTV proxy 90D"),("Estimated Uplift Assumption","+23.6%","Not an observed experiment"),("Observed Bonus Efficiency","Not available","Requires bonus-cost data"),("Predicted Risk Suppressions",f"{int(m.suppressed):,}","Fraud or RG score ≥55%")],ctx)
    segments=ctx.query(f"""SELECT 'High-value churn risk' Segment,COUNT(*) Players FROM v_player_scores v WHERE churn_probability>.65 AND predicted_ltv_90d>500 AND {active} UNION ALL SELECT 'New players',COUNT(*) FROM v_player_scores v WHERE registration_date>=:start AND registration_date<:end AND {active} UNION ALL SELECT 'Emerging VIP',COUNT(*) FROM v_player_scores v WHERE predicted_ltv_90d>1200 AND vip_level<>'Platinum' AND {active} UNION ALL SELECT 'Dormant 30D',COUNT(*) FROM v_player_scores v WHERE last_session<DATE(:end,'-30 day') AND (:country='All markets' OR v.country=:country) UNION ALL SELECT 'Bonus sensitive',COUNT(*) FROM v_player_scores v WHERE fraud_risk BETWEEN .25 AND .55 AND {active}""")
    if int(segments.Players.sum()) == 0:
        empty_state("No CRM segments match these filters")
        return
    left,middle,right=st.columns([1,1.7,1.4])
    with left:
        st.markdown("#### Dynamic SQL segments")
        for row in segments.itertuples(): insight(row.Segment,f"{row.Players:,} players","View segment")
    with middle:
        st.markdown("#### Journey governance flow");st.graphviz_chart('digraph G { rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fillcolor="#0a2730" color="#27d17f" fontcolor="white"]; a[label="TRIGGER"]; b[label="SAFETY CHECK"]; c[label="SEGMENT"]; d[label="CHANNEL"]; e[label="CONTROL"]; f[label="MEASURE"]; a->b->c->d->e->f; }',width="stretch");st.caption("Required control flow for every CRM activation; this diagram describes governance and is not a live campaign builder.")
    with right:
        queue=ctx.query(f"""SELECT player_id,recommended_action,predicted_ltv_90d,model_confidence FROM v_player_scores v WHERE fraud_risk<.55 AND rg_risk<.55 AND recommended_action<>'Monitor' AND {active} ORDER BY predicted_ltv_90d DESC,model_confidence DESC LIMIT 10""");st.markdown("#### Next best action");data_table(queue,column_config={"predicted_ltv_90d":st.column_config.NumberColumn("Predicted LTV proxy 90D",format="$%.0f"),"model_confidence":st.column_config.ProgressColumn("Predicted confidence",min_value=0,max_value=1,format="%.1%%")})
    exp=ctx.query("""SELECT 'Control' Variant,0 revenue,0 uplift UNION ALL SELECT 'Manual CRM',:revenue*.44,.108 UNION ALL SELECT 'AI decisioning',:revenue,.236""",{"revenue":float(m.revenue)})
    c1,c2=st.columns([2,1])
    with c1:
        fig=px.bar(exp,x="Variant",y="revenue",color="Variant",text="uplift",title="DEMO SCENARIO · NOT OBSERVED",color_discrete_sequence=["#556b7a",COLORS["cyan"],COLORS["green"]]);fig.update_traces(texttemplate="%{text:.1%}");chart(polish(fig,340,False),exp,explanation="Scenario based on explicit uplift assumptions; replace with controlled-experiment results when real campaign data is connected.")
    with c2: chart(polish(px.funnel(segments,x="Players",y="Segment",title="SEGMENT SIZES"),340,False),segments,explanation="Segments may overlap and therefore do not represent sequential funnel conversion.")
