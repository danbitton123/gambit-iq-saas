from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS
from queries.sportsbook import (
    bet_composition, daily_handle_by_sport, daily_mean_threshold,
    event_liability, metrics, sport_performance, top_event,
)
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight,kpis,money,pct,period_delta
from ui.theme import page_header


def render(ctx)->None:
    page_header("SPORTSBOOK CONTROL ROOM","Margin, exposure and live trading intelligence","Sportsbook")
    m=metrics.run(ctx); previous=metrics.run_previous(ctx)
    kpis([("Observed Sportsbook GGR",money(m.ggr),period_delta(m.ggr,previous.ggr)),("Observed Handle",money(m.handle),period_delta(m.handle,previous.handle)),("Observed Hold",pct(m.ggr/m.handle if m.handle else 0,2),"Observed GGR / handle"),("Observed Realized Downside",money(m.exposure),"Losses on settled bets"),("Observed Live Bets",f"{int(m.live):,}",period_delta(m.live,previous.live))],ctx)
    daily=daily_handle_by_sport.run(ctx);daily.date=pd.to_datetime(daily.date)
    if daily.empty:
        empty_state("No sportsbook activity matches these filters")
        return
    threshold=daily_mean_threshold.run(ctx)
    top=top_event.run(ctx)
    left,right=st.columns([3.1,1],gap="medium")
    with left:
        fig=px.line(daily,x="date",y="Exposure",color="sport",title="DAILY HANDLE BY SPORT · SQL");fig.add_hline(y=threshold,line_dash="dash",line_color=COLORS["red"],annotation_text="Daily mean");chart(polish(fig,400),daily,explanation="Lines show settled stake volume (handle), not open exposure. The dashed line is the filtered daily mean.")
    with right:
        st.markdown("<p class='panel-title'>Live Risk Feed</p>",unsafe_allow_html=True);insight("Odds movement anomaly","Rapid movement detected in a football market.","HIGH",True)
        if not top.empty:
            insight("Concentrated liability",f"{top.iloc[0].event_name} holds the largest settled handle.",money(top.iloc[0].exposure),True)
        else:
            insight("Concentrated liability","No settled events in this period.","—",True)
        insight("Sharp bettor alert","Unusual timing and stake concentration.","Manual review",True)
    sport=sport_performance.run(ctx)
    comp=bet_composition.run(ctx)
    events=event_liability.run(ctx)
    c1,c2,c3=st.columns([1.1,1,1.8],gap="medium")
    with c1: chart(polish(px.bar(sport,x="GGR",y="sport",orientation="h",color="Hold",title="SPORT PROFITABILITY",color_continuous_scale=[COLORS["red"],COLORS["gold"],COLORS["green"]]),330,False),sport,explanation="Red indicates lower observed hold; green indicates higher hold.")
    with c2: chart(polish(px.pie(comp,values="stake",names="Type",hole=.68,title="BETTING COMPOSITION",color_discrete_sequence=[COLORS["cyan"],COLORS["green"]]),330),comp,explanation="Share of settled handle by bet timing.")
    with c3:
        st.markdown("#### Event-level liability")
        data_table(events,column_config={"Exposure":st.column_config.NumberColumn("Handle",format="$%.0f"),"GGR":st.column_config.NumberColumn(format="$%.0f"),"Bets":st.column_config.NumberColumn(format="%d")})
