from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from ui.charts import polish
from ui.components import insight,kpis,money,pct
from ui.theme import page_header


def render(ctx)->None:
    page_header("SPORTSBOOK CONTROL ROOM","Margin, exposure and live trading intelligence","Sportsbook")
    m=ctx.query("""SELECT SUM(stake) handle,SUM(payout) payout,SUM(sportsbook_ggr) ggr,SUM(is_live) live,SUM(CASE WHEN sportsbook_ggr<0 THEN -sportsbook_ggr ELSE 0 END) exposure FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country)""").iloc[0]
    kpis([("Sportsbook GGR",money(m.ggr),"SQL SUM"),("Handle",money(m.handle),"SQL SUM"),("Hold %",pct(m.ggr/m.handle if m.handle else 0,2),"GGR / handle"),("Open Exposure",money(m.exposure),"Negative GGR"),("Live Bets",f"{int(m.live):,}","SQL filtered")])
    daily=ctx.query("""SELECT DATE(bet_date) date,sport,SUM(stake) Exposure,SUM(sportsbook_ggr) GGR FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY DATE(bet_date),sport ORDER BY date""");daily.date=pd.to_datetime(daily.date)
    threshold=ctx.scalar("""WITH d AS (SELECT DATE(bet_date),SUM(stake) x FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY DATE(bet_date)) SELECT AVG(x) FROM d""") or 0
    left,right=st.columns([3.1,1])
    with left:
        fig=px.line(daily,x="date",y="Exposure",color="sport",title="LIVE EXPOSURE BY SPORT · SQL");fig.add_hline(y=threshold,line_dash="dash",line_color=COLORS["red"],annotation_text="Daily mean");st.plotly_chart(polish(fig,400),width="stretch")
    with right:
        st.markdown("<p class='panel-title'>Live Risk Feed</p>",unsafe_allow_html=True);insight("Odds movement anomaly","Rapid movement detected in a football market.","HIGH",True);insight("Concentrated liability","Top events require review.",money(m.exposure*.42),True);insight("Sharp bettor alert","Unusual timing and stake concentration.","Manual review",True)
    sport=ctx.query("""SELECT sport,SUM(sportsbook_ggr) GGR,SUM(stake) Handle,COUNT(*) Bets,SUM(sportsbook_ggr)/NULLIF(SUM(stake),0) Hold FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY sport ORDER BY GGR""")
    comp=ctx.query("""SELECT CASE is_live WHEN 1 THEN 'Live' ELSE 'Pre-match' END Type,SUM(stake) stake FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY is_live""")
    events=ctx.query("""WITH e AS (SELECT event_name,sport,SUM(stake) Exposure,SUM(sportsbook_ggr) GGR,COUNT(*) Bets FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name,sport), q AS (SELECT AVG(Exposure) avg_exp FROM e) SELECT e.*,CASE WHEN Exposure>avg_exp*1.5 THEN 'HIGH' WHEN Exposure>avg_exp THEN 'MEDIUM' ELSE 'LOW' END Status FROM e CROSS JOIN q ORDER BY Exposure DESC""")
    c1,c2,c3=st.columns([1.1,1,1.8])
    with c1: st.plotly_chart(polish(px.bar(sport,x="GGR",y="sport",orientation="h",color="Hold",title="SPORT PROFITABILITY",color_continuous_scale=[COLORS["red"],COLORS["gold"],COLORS["green"]]),330,False),width="stretch")
    with c2: st.plotly_chart(polish(px.pie(comp,values="stake",names="Type",hole=.68,title="BETTING COMPOSITION",color_discrete_sequence=[COLORS["cyan"],COLORS["green"]]),330),width="stretch")
    with c3: st.markdown("#### Event-level liability");st.dataframe(events,width="stretch",hide_index=True)
