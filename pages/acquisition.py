from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money,pct,period_delta
from ui.theme import page_header

COST="CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END"

def render(ctx)->None:
    page_header("ACQUISITION INTELLIGENCE","Traffic quality, LTV and marketing profitability","Growth Analytics")
    base=f"""WITH ftd AS (SELECT player_id,MIN(transaction_date) ftd_date FROM transactions WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id), b AS (SELECT p.*,v.predicted_ltv_90d,v.churn_probability,v.fraud_risk,CASE WHEN ftd.ftd_date>=:start AND ftd.ftd_date<:end THEN ftd.ftd_date END ftd_date,{COST} acquisition_cost FROM players p JOIN v_player_scores v USING(player_id) LEFT JOIN ftd USING(player_id) WHERE p.registration_date>=:start AND p.registration_date<:end AND (:country='All markets' OR p.country=:country)) """
    metric_sql=base+"SELECT COALESCE(SUM(ftd_date IS NOT NULL),0) depositors,1.0*SUM(ftd_date IS NOT NULL)/NULLIF(COUNT(*),0) conversion,AVG(acquisition_cost) cac,AVG(predicted_ltv_90d/acquisition_cost) roas,AVG(fraud_risk>=.55) fraud FROM b"
    m=ctx.query(metric_sql).iloc[0]; previous=ctx.previous_query(metric_sql).iloc[0]
    roas_value = f"{m.roas:.1f}x" if m.roas is not None and m.roas == m.roas else "—"
    kpis([("New Depositors",f"{int(m.depositors or 0):,}",period_delta(m.depositors,previous.depositors)),("FTD Conversion",pct(m.conversion),"FTD in period / registrations"),("Estimated CAC",money(m.cac,False),"Demo channel-cost assumption"),("Predicted ROAS 90D",roas_value,"Predicted LTV / estimated CAC"),("High Fraud-Risk Rate",pct(m.fraud,2),"Registered players ≥55% score")])
    source=ctx.query(base+"""SELECT channel,COUNT(*) Players,SUM(ftd_date IS NOT NULL) FTD,AVG(acquisition_cost) CAC,AVG(predicted_ltv_90d) Predicted_LTV,AVG(predicted_ltv_90d/acquisition_cost) Predicted_ROAS,AVG(fraud_risk) Fraud_Risk,1-AVG(churn_probability) D30_Retention,100*AVG(predicted_ltv_90d/acquisition_cost)*(1-AVG(churn_probability))*(1-AVG(fraud_risk))/10 Quality_Score FROM b GROUP BY channel ORDER BY Quality_Score DESC""")
    if source.empty:
        empty_state("No registrations match these filters")
        return
    left,right=st.columns([3,1])
    with left:
        fig=px.scatter(source,x="Players",y="Predicted_LTV",size="FTD",color="Quality_Score",text="channel",title="SOURCE QUALITY MATRIX · SQL + ML",color_continuous_scale=[COLORS["red"],COLORS["gold"],COLORS["green"]]);fig.update_traces(textposition="top center");chart(polish(fig,390,False),source,explanation="Bubble size is observed FTD; color is a demo composite score using predicted LTV, churn and fraud risk.")
    with right:
        best,worst=source.iloc[0],source.iloc[-1];st.markdown("<p class='panel-title'>Budget Recommendations</p>",unsafe_allow_html=True);insight(f"Scale {best.channel}","Strong quality-adjusted predicted value.","+18% suggested");insight(f"Reduce {worst.channel}","Weaker risk-adjusted efficiency.","-12% suggested",True)
    st.markdown("#### Acquisition source performance");data_table(source,column_config={"CAC":st.column_config.NumberColumn("Estimated CAC",format="$%.0f"),"Predicted_LTV":st.column_config.NumberColumn("Predicted LTV",format="$%.0f"),"Predicted_ROAS":st.column_config.NumberColumn("Predicted ROAS",format="%.2fx"),"Fraud_Risk":st.column_config.ProgressColumn("Fraud risk",min_value=0,max_value=1,format="%.1%%"),"D30_Retention":st.column_config.ProgressColumn("Modelled retention",min_value=0,max_value=1,format="%.1%%"),"Quality_Score":st.column_config.NumberColumn("Demo quality score",format="%.1f")})
    funnel=ctx.query(base+"SELECT COUNT(*)*13 Visits,COUNT(*) Registrations,SUM(kyc_status='Verified') KYC,SUM(ftd_date IS NOT NULL) FTD,CAST(SUM(ftd_date IS NOT NULL)*.61 AS INT) SecondDeposit FROM b").iloc[0]
    fig=go.Figure(go.Funnel(y=["Estimated visits","Registrations","KYC verified","First deposit","Estimated second deposit"],x=funnel.tolist(),marker={"color":[COLORS["cyan"],"#269fbd",COLORS["green"],COLORS["gold"],"#d68b28"]},textinfo="value+percent initial"));fig.update_layout(title="ACQUISITION CONVERSION FUNNEL");chart(polish(fig,350,False),explanation="Registrations, KYC and FTD are observed. Visits and second deposits are explicitly marked as demo estimates because no event-level source exists yet.")
