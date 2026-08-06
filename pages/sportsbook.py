from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money,pct,period_delta
from ui.theme import page_header


def render(ctx)->None:
    page_header("SPORTSBOOK CONTROL ROOM","Margin, exposure and live trading intelligence","Sportsbook")
    metric_sql="""SELECT COALESCE(SUM(stake),0) handle,COALESCE(SUM(payout),0) payout,COALESCE(SUM(sportsbook_ggr),0) ggr,COALESCE(SUM(is_live),0) live,COALESCE(SUM(CASE WHEN sportsbook_ggr<0 THEN -sportsbook_ggr ELSE 0 END),0) exposure FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country)"""
    m=ctx.query(metric_sql).iloc[0]; previous=ctx.previous_query(metric_sql).iloc[0]
    kpis([("Observed Sportsbook GGR",money(m.ggr),period_delta(m.ggr,previous.ggr)),("Observed Handle",money(m.handle),period_delta(m.handle,previous.handle)),("Observed Hold",pct(m.ggr/m.handle if m.handle else 0,2),"Observed GGR / handle"),("Observed Realized Downside",money(m.exposure),"Losses on settled bets"),("Observed Live Bets",f"{int(m.live):,}",period_delta(m.live,previous.live))],ctx)
    daily=ctx.query("""SELECT DATE(bet_date) date,sport,SUM(stake) Exposure,SUM(sportsbook_ggr) GGR FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY DATE(bet_date),sport ORDER BY date""");daily.date=pd.to_datetime(daily.date)
    if daily.empty:
        empty_state("No sportsbook activity matches these filters")
        return
    threshold=ctx.scalar("""WITH d AS (SELECT DATE(bet_date),SUM(stake) x FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY DATE(bet_date)) SELECT AVG(x) FROM d""") or 0
    top_event=ctx.query("""SELECT event_name,SUM(stake) exposure FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name ORDER BY exposure DESC LIMIT 1""")
    left,right=st.columns([3.1,1])
    with left:
        fig=px.line(daily,x="date",y="Exposure",color="sport",title="DAILY HANDLE BY SPORT · SQL");fig.add_hline(y=threshold,line_dash="dash",line_color=COLORS["red"],annotation_text="Daily mean");chart(polish(fig,400),daily,explanation="Lines show settled stake volume (handle), not open exposure. The dashed line is the filtered daily mean.")
    with right:
        st.markdown("<p class='panel-title'>Live Risk Feed</p>",unsafe_allow_html=True);insight("Odds movement anomaly","Rapid movement detected in a football market.","HIGH",True)
        if not top_event.empty:
            insight("Concentrated liability",f"{top_event.iloc[0].event_name} holds the largest settled handle.",money(top_event.iloc[0].exposure),True)
        else:
            insight("Concentrated liability","No settled events in this period.","—",True)
        insight("Sharp bettor alert","Unusual timing and stake concentration.","Manual review",True)
    sport=ctx.query("""SELECT sport,SUM(sportsbook_ggr) GGR,SUM(stake) Handle,COUNT(*) Bets,SUM(sportsbook_ggr)/NULLIF(SUM(stake),0) Hold FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY sport ORDER BY GGR""")
    comp=ctx.query("""SELECT CASE is_live WHEN 1 THEN 'Live' ELSE 'Pre-match' END Type,SUM(stake) stake FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY is_live""")
    events=ctx.query("""WITH e AS (SELECT event_name,sport,SUM(stake) Exposure,SUM(sportsbook_ggr) GGR,COUNT(*) Bets FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name,sport), q AS (SELECT AVG(Exposure) avg_exp FROM e) SELECT e.*,CASE WHEN Exposure>avg_exp*1.5 THEN 'HIGH' WHEN Exposure>avg_exp THEN 'MEDIUM' ELSE 'LOW' END Status FROM e CROSS JOIN q ORDER BY Exposure DESC""")
    c1,c2,c3=st.columns([1.1,1,1.8])
    with c1: chart(polish(px.bar(sport,x="GGR",y="sport",orientation="h",color="Hold",title="SPORT PROFITABILITY",color_continuous_scale=[COLORS["red"],COLORS["gold"],COLORS["green"]]),330,False),sport,explanation="Red indicates lower observed hold; green indicates higher hold.")
    with c2: chart(polish(px.pie(comp,values="stake",names="Type",hole=.68,title="BETTING COMPOSITION",color_discrete_sequence=[COLORS["cyan"],COLORS["green"]]),330),comp,explanation="Share of settled handle by bet timing.")
    with c3:
        st.markdown("#### Event-level liability")
        data_table(events,column_config={"Exposure":st.column_config.NumberColumn("Handle",format="$%.0f"),"GGR":st.column_config.NumberColumn(format="$%.0f"),"Bets":st.column_config.NumberColumn(format="%d")})
