from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import COLORS
from queries.acquisition import ftd, ftd_conversion_d30, funnel, metrics, source_performance
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money,pct,period_delta
from ui.theme import page_header

def render(ctx)->None:
    page_header("ACQUISITION INTELLIGENCE","Traffic quality, LTV and marketing profitability","Growth Analytics")
    m=metrics.run(ctx); previous=metrics.run_previous(ctx)
    ftd_now=ftd.run(ctx);previous_ftd=ftd.run_previous(ctx)
    conversion=ftd_conversion_d30.run(ctx)
    roas_value = f"{m.roas:.1f}x" if m.roas is not None and m.roas == m.roas else "—"
    kpis([("Observed FTD",f"{int(ftd_now.ftd_count or 0):,}",period_delta(ftd_now.ftd_count,previous_ftd.ftd_count)),("Observed FTD Conversion D30",pct(conversion.ftd_conversion_d30),f"{int(conversion.converted_d30 or 0):,} / {int(conversion.eligible_registrations or 0):,} mature registrations"),("Estimated CAC",money(m.cac,False),"Demo channel-cost assumption"),("Predicted ROAS Proxy 90D",roas_value,"LTV proxy / estimated CAC"),("Predicted High Fraud-Risk Rate",pct(m.fraud,2),"Mature registrations ≥55% score")],ctx)
    source=source_performance.run(ctx)
    if source.empty:
        empty_state("No registrations match these filters")
        return
    left,right=st.columns([3,1],gap="medium")
    with left:
        fig=px.scatter(source,x="Players",y="Predicted_LTV_Proxy",size="FTD_D30",color="Quality_Score",text="channel",title="SOURCE QUALITY MATRIX · SQL + ML",color_continuous_scale=[COLORS["red"],COLORS["gold"],COLORS["green"]]);fig.update_traces(textposition="top center");chart(polish(fig,390,False),source,explanation="Bubble size is observed FTD within 30 days for mature registration cohorts; color is a demo composite score using predicted proxies.")
    with right:
        best,worst=source.iloc[0],source.iloc[-1];st.markdown("<p class='panel-title'>Budget Review Priorities</p>",unsafe_allow_html=True);insight(f"Review scaling {best.channel}","Highest quality-adjusted predicted proxy in the filtered mature cohort.","Rank #1");insight(f"Review {worst.channel}","Lowest quality-adjusted predicted proxy; validate before reallocating budget.","Lowest rank",True)
    st.markdown("#### Acquisition source performance");data_table(source,column_config={"FTD_Conversion_D30":st.column_config.ProgressColumn("Observed FTD conversion D30",min_value=0,max_value=1,format="%.1%%"),"CAC":st.column_config.NumberColumn("Estimated CAC",format="$%.0f"),"Predicted_LTV_Proxy":st.column_config.NumberColumn("Predicted LTV proxy 90D",format="$%.0f"),"Predicted_ROAS_Proxy":st.column_config.NumberColumn("Predicted ROAS proxy",format="%.2fx"),"Fraud_Risk":st.column_config.ProgressColumn("Predicted fraud risk",min_value=0,max_value=1,format="%.1%%"),"Predicted_Retention_Proxy":st.column_config.ProgressColumn("Predicted retention proxy",min_value=0,max_value=1,format="%.1%%"),"Quality_Score":st.column_config.NumberColumn("Estimated quality score",format="%.1f")})
    funnel_row=funnel.run(ctx)
    fig=go.Figure(go.Funnel(y=["Estimated visits","Mature registrations","KYC verified","Observed FTD D30","Estimated second deposit"],x=funnel_row.tolist(),marker={"color":[COLORS["cyan"],"#269fbd",COLORS["green"],COLORS["gold"],"#d68b28"]},textinfo="value+percent initial"));fig.update_layout(title="ACQUISITION CONVERSION FUNNEL");chart(polish(fig,350,False),explanation="Registration cohorts have a complete 30-day observation window. KYC and FTD D30 are observed; visits and second deposits remain explicit demo estimates.")
