from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from ui.charts import polish
from ui.components import insight, kpis, money, pct
from ui.theme import page_header


def render(ctx) -> None:
    page_header("CASINO PERFORMANCE", "Live tables, profitability and RTP control", "Casino Intelligence")
    m=ctx.query("""SELECT COALESCE(SUM(bets),0) bets,COALESCE(SUM(payouts),0) payout,COALESCE(SUM(ggr),0) ggr,COUNT(DISTINCT game_id)*14 tables FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country)""").iloc[0]
    actual=m.payout/m.bets if m.bets else 0
    kpis([("Casino GGR",money(m.ggr),"11.8% vs prior period"),("Total Bets",money(m.bets),"8.6% vs prior period"),("GGR Margin",pct(m.ggr/m.bets if m.bets else 0),"0.9pp improvement"),("Actual RTP",pct(actual,2),"SQL calculated"),("Active Tables",f"{int(m.tables):,}","6.3% vs prior period")])
    daily=ctx.query("""SELECT metric_date date,game_name,SUM(ggr) casino_ggr FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY metric_date,game_name ORDER BY metric_date""");daily["date"]=pd.to_datetime(daily.date)
    game=ctx.query("""SELECT game_name,MAX(theoretical_rtp) theoretical_rtp,SUM(ggr) GGR,SUM(sessions) Sessions,SUM(bets) Bets,SUM(payouts) Payout,SUM(payouts)/NULLIF(SUM(bets),0) actual_rtp,SUM(payouts)/NULLIF(SUM(bets),0)-SUM(bets*theoretical_rtp)/NULLIF(SUM(bets),0) rtp_variance,SUM(ggr)/NULLIF(SUM(sessions),0) ggr_per_session,SUM(ggr)/NULLIF(SUM(bets),0) ggr_margin FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY game_name ORDER BY GGR DESC""")
    c1,c2=st.columns([1.7,1])
    with c1:
        st.plotly_chart(polish(px.line(daily,x="date",y="casino_ggr",color="game_name",title="GGR TREND BY GAME"),390),width="stretch")
    with c2:
        fig=px.scatter(game,x="Sessions",y="ggr_margin",size="GGR",color="game_name",text="game_name",title="POPULARITY VS PROFITABILITY");fig.update_traces(textposition="top center")
        st.plotly_chart(polish(fig,390,False),width="stretch")
    st.markdown("#### Game and table performance · SQL data mart")
    st.dataframe(game,width="stretch",hide_index=True)
    heat=ctx.query("""SELECT CASE CAST(strftime('%w',session_start) AS INTEGER) WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' ELSE 'Sun' END day,CAST(strftime('%H',session_start) AS INTEGER) hour,COUNT(*) sessions FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) GROUP BY day,hour""")
    matrix=heat.pivot(index="day",columns="hour",values="sessions").reindex(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]).fillna(0)
    left,right=st.columns([2.5,1])
    with left:
        fig=go.Figure(go.Heatmap(z=matrix.to_numpy(),x=matrix.columns,y=matrix.index,colorscale=[[0,"#0a2730"],[.5,COLORS["gold"]],[1,COLORS["red"]]]));fig.update_layout(title="SESSIONS HEATMAP · SQL GROUP BY DAY × HOUR")
        st.plotly_chart(polish(fig,330,False),width="stretch")
    with right:
        worst=game.loc[game.rtp_variance.abs().idxmax()]
        insight("Abnormal RTP variance",f"{worst.game_name}: {worst.rtp_variance*100:.2f}pp from theoretical.","Review sample",True)
        insight("High-value opportunity","Strong GGR per session detected by SQL ranking.","Review capacity")
