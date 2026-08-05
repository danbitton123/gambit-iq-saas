from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import COLORS
from ui.charts import polish
from ui.components import insight,kpis,money,pct
from ui.theme import page_header

COST="CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END"

def render(ctx)->None:
    page_header("ACQUISITION INTELLIGENCE","Traffic quality, LTV and marketing profitability","Growth Analytics")
    base=f"""WITH ftd AS (SELECT player_id,MIN(transaction_date) ftd_date FROM transactions WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id), b AS (SELECT p.*,v.predicted_ltv_90d,v.churn_probability,v.fraud_risk,ftd.ftd_date,{COST} acquisition_cost FROM players p JOIN v_player_scores v USING(player_id) LEFT JOIN ftd USING(player_id) WHERE (:country='All markets' OR p.country=:country)) """
    m=ctx.query(base+"SELECT SUM(ftd_date IS NOT NULL) depositors,1.0*SUM(ftd_date IS NOT NULL)/COUNT(*) conversion,AVG(acquisition_cost) cac,AVG(predicted_ltv_90d/acquisition_cost) roas,AVG(fraud_risk>=.55) fraud FROM b").iloc[0]
    kpis([("New Depositors",f"{int(m.depositors):,}","Approved first deposits"),("FTD Conversion",pct(m.conversion),"FTD / registrations"),("Average CAC",money(m.cac,False),"SQL channel cost"),("Predicted ROAS 90D",f"{m.roas:.1f}x","ML LTV / CAC"),("Affiliate Fraud Rate",pct(m.fraud,2),"ML classification")])
    source=ctx.query(base+"""SELECT channel,COUNT(*) Players,SUM(ftd_date IS NOT NULL) FTD,AVG(acquisition_cost) CAC,AVG(predicted_ltv_90d) Predicted_LTV,AVG(predicted_ltv_90d/acquisition_cost) Predicted_ROAS,AVG(fraud_risk) Fraud_Risk,1-AVG(churn_probability) D30_Retention,100*AVG(predicted_ltv_90d/acquisition_cost)*(1-AVG(churn_probability))*(1-AVG(fraud_risk))/10 Quality_Score FROM b GROUP BY channel ORDER BY Quality_Score DESC""")
    left,right=st.columns([3,1])
    with left:
        fig=px.scatter(source,x="Players",y="Predicted_LTV",size="FTD",color="Quality_Score",text="channel",title="AFFILIATE QUALITY MATRIX · SQL + ML",color_continuous_scale=[COLORS["red"],COLORS["gold"],COLORS["green"]]);fig.update_traces(textposition="top center");st.plotly_chart(polish(fig,390,False),width="stretch")
    with right:
        best,worst=source.iloc[0],source.iloc[-1];st.markdown("<p class='panel-title'>Budget Recommendations</p>",unsafe_allow_html=True);insight(f"Scale {best.channel}","Strong quality-adjusted predicted value.","+18% suggested");insight(f"Reduce {worst.channel}","Weaker risk-adjusted efficiency.","-12% suggested",True)
    st.markdown("#### Acquisition source performance");st.dataframe(source,width="stretch",hide_index=True)
    funnel=ctx.query(base+"SELECT COUNT(*)*13 Visits,COUNT(*) Registrations,SUM(kyc_status='Verified') KYC,SUM(ftd_date IS NOT NULL) FTD,CAST(SUM(ftd_date IS NOT NULL)*.61 AS INT) SecondDeposit FROM b").iloc[0]
    fig=go.Figure(go.Funnel(y=["Visits","Registrations","KYC verified","First deposit","Second deposit"],x=funnel.tolist(),marker={"color":[COLORS["cyan"],"#269fbd",COLORS["green"],COLORS["gold"],"#d68b28"]},textinfo="value+percent initial"));fig.update_layout(title="ACQUISITION CONVERSION FUNNEL · SQL");st.plotly_chart(polish(fig,350,False),width="stretch")
