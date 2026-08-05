from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import COLORS
from data.kpi_queries import OBSERVED_FTD_CONVERSION_D30_SQL, OBSERVED_FTD_SQL
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money,pct,period_delta
from ui.theme import page_header

COST="CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END"

def render(ctx)->None:
    page_header("ACQUISITION INTELLIGENCE","Traffic quality, LTV and marketing profitability","Growth Analytics")
    first_deposit="""WITH ftd AS (SELECT player_id,MIN(transaction_date) ftd_date FROM transactions WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id) """
    base=first_deposit+f""", b AS (SELECT p.*,v.predicted_ltv_90d,v.churn_probability,v.fraud_risk,ftd.ftd_date,CASE WHEN ftd.ftd_date>=p.registration_date AND ftd.ftd_date<DATETIME(p.registration_date,'+30 days') THEN 1 ELSE 0 END converted_d30,{COST} acquisition_cost FROM players p JOIN v_player_scores v USING(player_id) LEFT JOIN ftd USING(player_id) WHERE p.registration_date>=:start AND p.registration_date<:end AND p.registration_date<=DATETIME(:end,'-30 days') AND (:country='All markets' OR p.country=:country)) """
    metric_sql=base+"SELECT AVG(acquisition_cost) cac,AVG(predicted_ltv_90d/acquisition_cost) roas,AVG(fraud_risk>=.55) fraud FROM b"
    m=ctx.query(metric_sql).iloc[0]; previous=ctx.previous_query(metric_sql).iloc[0]
    ftd=ctx.query(OBSERVED_FTD_SQL).iloc[0];previous_ftd=ctx.previous_query(OBSERVED_FTD_SQL).iloc[0]
    conversion=ctx.query(OBSERVED_FTD_CONVERSION_D30_SQL).iloc[0]
    roas_value = f"{m.roas:.1f}x" if m.roas is not None and m.roas == m.roas else "Missing data"
    kpis([("Observed FTD",f"{int(ftd.ftd_count or 0):,}",period_delta(ftd.ftd_count,previous_ftd.ftd_count)),("Observed FTD Conversion D30",pct(conversion.ftd_conversion_d30),f"{int(conversion.converted_d30 or 0):,} / {int(conversion.eligible_registrations or 0):,} mature registrations"),("Estimated CAC",money(m.cac,False),"Demo channel-cost assumption"),("Predicted ROAS Proxy 90D",roas_value,"LTV proxy / estimated CAC"),("Predicted High Fraud-Risk Rate",pct(m.fraud,2),"Mature registrations ≥55% score")],ctx)
    source=ctx.query(base+"""SELECT channel,COUNT(*) Players,SUM(converted_d30) FTD_D30,1.0*SUM(converted_d30)/NULLIF(COUNT(*),0) FTD_Conversion_D30,AVG(acquisition_cost) CAC,AVG(predicted_ltv_90d) Predicted_LTV_Proxy,AVG(predicted_ltv_90d/acquisition_cost) Predicted_ROAS_Proxy,AVG(fraud_risk) Fraud_Risk,1-AVG(churn_probability) Predicted_Retention_Proxy,100*AVG(predicted_ltv_90d/acquisition_cost)*(1-AVG(churn_probability))*(1-AVG(fraud_risk))/10 Quality_Score FROM b GROUP BY channel ORDER BY Quality_Score DESC""")
    if source.empty:
        empty_state("No registrations match these filters")
        return
    left,right=st.columns([3,1])
    with left:
        fig=px.scatter(source,x="Players",y="Predicted_LTV_Proxy",size="FTD_D30",color="Quality_Score",text="channel",title="SOURCE QUALITY MATRIX · SQL + ML",color_continuous_scale=[COLORS["red"],COLORS["gold"],COLORS["green"]]);fig.update_traces(textposition="top center");chart(polish(fig,390,False),source,explanation="Bubble size is observed FTD within 30 days for mature registration cohorts; color is a demo composite score using predicted proxies.")
    with right:
        best,worst=source.iloc[0],source.iloc[-1];st.markdown("<p class='panel-title'>Budget Review Priorities</p>",unsafe_allow_html=True);insight(f"Review scaling {best.channel}","Highest quality-adjusted predicted proxy in the filtered mature cohort.","Rank #1");insight(f"Review {worst.channel}","Lowest quality-adjusted predicted proxy; validate before reallocating budget.","Lowest rank",True)
    st.markdown("#### Acquisition source performance");data_table(source,column_config={"FTD_Conversion_D30":st.column_config.ProgressColumn("Observed FTD conversion D30",min_value=0,max_value=1,format="%.1%%"),"CAC":st.column_config.NumberColumn("Estimated CAC",format="$%.0f"),"Predicted_LTV_Proxy":st.column_config.NumberColumn("Predicted LTV proxy 90D",format="$%.0f"),"Predicted_ROAS_Proxy":st.column_config.NumberColumn("Predicted ROAS proxy",format="%.2fx"),"Fraud_Risk":st.column_config.ProgressColumn("Predicted fraud risk",min_value=0,max_value=1,format="%.1%%"),"Predicted_Retention_Proxy":st.column_config.ProgressColumn("Predicted retention proxy",min_value=0,max_value=1,format="%.1%%"),"Quality_Score":st.column_config.NumberColumn("Estimated quality score",format="%.1f")})
    funnel=ctx.query(base+"SELECT COUNT(*)*13 Visits,COUNT(*) Registrations,SUM(kyc_status='Verified') KYC,SUM(converted_d30) FTD,CAST(SUM(converted_d30)*.61 AS INT) SecondDeposit FROM b").iloc[0]
    fig=go.Figure(go.Funnel(y=["Estimated visits","Mature registrations","KYC verified","Observed FTD D30","Estimated second deposit"],x=funnel.tolist(),marker={"color":[COLORS["cyan"],"#269fbd",COLORS["green"],COLORS["gold"],"#d68b28"]},textinfo="value+percent initial"));fig.update_layout(title="ACQUISITION CONVERSION FUNNEL");chart(polish(fig,350,False),explanation="Registration cohorts have a complete 30-day observation window. KYC and FTD D30 are observed; visits and second deposits remain explicit demo estimates.")
