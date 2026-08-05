from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight, kpis, money, pct, period_delta
from ui.theme import page_header


def render(ctx) -> None:
    page_header("CASINO PERFORMANCE", "Live tables, profitability and RTP control", "Casino Intelligence")
    metric_sql="""SELECT COALESCE(SUM(bets),0) bets,COALESCE(SUM(payouts),0) payout,COALESCE(SUM(ggr),0) ggr,COUNT(DISTINCT game_id) games FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country)"""
    m=ctx.query(metric_sql).iloc[0]; previous=ctx.previous_query(metric_sql).iloc[0]
    actual=m.payout/m.bets if m.bets else 0
    kpis([("Casino GGR",money(m.ggr),period_delta(m.ggr,previous.ggr)),("Total Bets",money(m.bets),period_delta(m.bets,previous.bets)),("GGR Margin",pct(m.ggr/m.bets if m.bets else 0),"Observed GGR / bets"),("Actual RTP",pct(actual,2),"Observed payouts / bets"),("Active Games",f"{int(m.games):,}","Games with activity")])
    daily=ctx.query("""SELECT metric_date date,game_name,SUM(ggr) casino_ggr FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY metric_date,game_name ORDER BY metric_date""");daily["date"]=pd.to_datetime(daily.date)
    game=ctx.query("""SELECT game_name,MAX(theoretical_rtp) theoretical_rtp,SUM(ggr) GGR,SUM(sessions) Sessions,SUM(bets) Bets,SUM(payouts) Payout,SUM(payouts)/NULLIF(SUM(bets),0) actual_rtp,SUM(payouts)/NULLIF(SUM(bets),0)-SUM(bets*theoretical_rtp)/NULLIF(SUM(bets),0) rtp_variance,SUM(ggr)/NULLIF(SUM(sessions),0) ggr_per_session,SUM(ggr)/NULLIF(SUM(bets),0) ggr_margin FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY game_name ORDER BY GGR DESC""")
    if game.empty:
        empty_state("No casino activity matches these filters")
        return
    c1,c2=st.columns([1.7,1])
    with c1:
        chart(polish(px.line(daily,x="date",y="casino_ggr",color="game_name",title="GGR TREND BY GAME"),390),daily,explanation="Observed daily GGR. Use the legend to isolate a game.")
    with c2:
        fig=px.scatter(game,x="Sessions",y="ggr_margin",size="GGR",color="game_name",text="game_name",title="POPULARITY VS PROFITABILITY");fig.update_traces(textposition="top center")
        chart(polish(fig,390,False),game,explanation="Bubble size is observed GGR; vertical position is observed GGR margin.")
    st.markdown("#### Game and table performance · SQL data mart")
    data_table(game,column_config={"GGR":st.column_config.NumberColumn(format="$%.0f"),"Bets":st.column_config.NumberColumn(format="$%.0f"),"Payout":st.column_config.NumberColumn(format="$%.0f"),"theoretical_rtp":st.column_config.NumberColumn("Theoretical RTP",format="%.2%%"),"actual_rtp":st.column_config.NumberColumn("Actual RTP",format="%.2%%"),"rtp_variance":st.column_config.NumberColumn("RTP variance",format="%+.2%%"),"ggr_per_session":st.column_config.NumberColumn("GGR / session",format="$%.2f"),"ggr_margin":st.column_config.NumberColumn("GGR margin",format="%.2%%")})
    heat=ctx.query("""SELECT CASE CAST(strftime('%w',session_start) AS INTEGER) WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' ELSE 'Sun' END day,CAST(strftime('%H',session_start) AS INTEGER) hour,COUNT(*) sessions FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) GROUP BY day,hour""")
    matrix=heat.pivot(index="day",columns="hour",values="sessions").reindex(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]).fillna(0)
    left,right=st.columns([2.5,1])
    with left:
        fig=go.Figure(go.Heatmap(z=matrix.to_numpy(),x=matrix.columns,y=matrix.index,colorscale=[[0,"#0a2730"],[.5,COLORS["gold"]],[1,COLORS["red"]]]));fig.update_layout(title="SESSIONS HEATMAP · SQL GROUP BY DAY × HOUR")
        chart(polish(fig,330,False),heat,explanation="Darker red indicates more observed sessions; it does not indicate worse performance.")
    with right:
        worst=game.loc[game.rtp_variance.abs().idxmax()]
        insight("Abnormal RTP variance",f"{worst.game_name}: {worst.rtp_variance*100:.2f}pp from theoretical.","Review sample",True)
        insight("High-value opportunity","Strong GGR per session detected by SQL ranking.","Review capacity")
