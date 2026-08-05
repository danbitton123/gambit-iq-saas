from __future__ import annotations
import plotly.express as px
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import insight,kpis,money
from ui.theme import page_header

def render(ctx)->None:
    page_header("PLAYER ACTIVATION STUDIO","Segments, journeys and next best action","CRM Automation")
    m=ctx.query("""SELECT SUM(fraud_risk<.55 AND rg_risk<.55) targetable,SUM(NOT(fraud_risk<.55 AND rg_risk<.55)) suppressed,SUM(CASE WHEN fraud_risk<.55 AND rg_risk<.55 AND recommended_action IN ('Retention review','VIP review') THEN predicted_ltv_90d*.08 ELSE 0 END) revenue FROM v_player_scores WHERE (:country='All markets' OR country=:country)""").iloc[0]
    kpis([("Players Targetable",f"{int(m.targetable):,}","Safety filtered"),("Campaign Revenue",money(m.revenue),"Modelled opportunity"),("Incremental Uplift","+23.6%","Experiment assumption"),("Bonus Efficiency","$3.42","Revenue / bonus"),("Suppressed for Risk",f"{int(m.suppressed):,}","Guardrails active")])
    segments=ctx.query("""SELECT 'High-value churn risk' Segment,COUNT(*) Players FROM v_player_scores WHERE churn_probability>.65 AND predicted_ltv_90d>500 AND (:country='All markets' OR country=:country) UNION ALL SELECT 'New players',COUNT(*) FROM v_player_scores WHERE registration_date>=DATE(:end,'-30 day') AND (:country='All markets' OR country=:country) UNION ALL SELECT 'Emerging VIP',COUNT(*) FROM v_player_scores WHERE predicted_ltv_90d>1200 AND vip_level<>'Platinum' AND (:country='All markets' OR country=:country) UNION ALL SELECT 'Dormant 30D',COUNT(*) FROM v_player_scores WHERE last_session<DATE(:end,'-30 day') AND (:country='All markets' OR country=:country) UNION ALL SELECT 'Bonus sensitive',COUNT(*) FROM v_player_scores WHERE fraud_risk BETWEEN .25 AND .55 AND (:country='All markets' OR country=:country)""")
    left,middle,right=st.columns([1,1.7,1.4])
    with left:
        st.markdown("#### Dynamic SQL segments")
        for row in segments.itertuples(): insight(row.Segment,f"{row.Players:,} players","View segment")
    with middle:
        st.markdown("#### Journey builder");st.graphviz_chart('digraph G { rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fillcolor="#0a2730" color="#27d17f" fontcolor="white"]; a[label="TRIGGER"]; b[label="SAFETY CHECK"]; c[label="SEGMENT"]; d[label="CHANNEL"]; e[label="CONTROL"]; f[label="MEASURE"]; a->b->c->d->e->f; }',width="stretch")
    with right:
        queue=ctx.query("""SELECT player_id,recommended_action,predicted_ltv_90d,model_confidence FROM v_player_scores WHERE fraud_risk<.55 AND rg_risk<.55 AND recommended_action<>'Monitor' AND (:country='All markets' OR country=:country) ORDER BY predicted_ltv_90d DESC,model_confidence DESC LIMIT 10""");st.markdown("#### Next best action");st.dataframe(queue,hide_index=True,width="stretch")
    exp=ctx.query("""SELECT 'Control' Variant,0 revenue,0 uplift UNION ALL SELECT 'Manual CRM',:revenue*.44,.108 UNION ALL SELECT 'AI decisioning',:revenue,.236""",{"revenue":float(m.revenue)})
    c1,c2=st.columns([2,1])
    with c1:
        fig=px.bar(exp,x="Variant",y="revenue",color="Variant",text="uplift",title="EXPERIMENT RESULTS",color_discrete_sequence=["#556b7a",COLORS["cyan"],COLORS["green"]]);fig.update_traces(texttemplate="%{text:.1%}");st.plotly_chart(polish(fig,340,False),width="stretch")
    with c2: st.plotly_chart(polish(px.funnel(segments,x="Players",y="Segment",title="JOURNEY ELIGIBILITY"),340,False),width="stretch")
