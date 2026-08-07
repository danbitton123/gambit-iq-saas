from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from queries.casino import daily_ggr_by_game, game_performance, metrics, sessions_heatmap
from ui.charts import polish
from ui.components import chart, data_table, empty_state, insight, kpis, money, pct, period_delta
from ui.theme import page_header


def render(ctx) -> None:
    page_header("CASINO PERFORMANCE", "Live tables, profitability and RTP control", "Casino Intelligence")
    m=metrics.run(ctx); previous=metrics.run_previous(ctx)
    actual=m.payout/m.bets if m.bets else 0
    kpis([("Observed Casino GGR",money(m.ggr),period_delta(m.ggr,previous.ggr)),("Observed Total Bets",money(m.bets),period_delta(m.bets,previous.bets)),("Observed GGR Margin",pct(m.ggr/m.bets if m.bets else 0),"Observed GGR / bets"),("Observed Actual RTP",pct(actual,2),"Observed payouts / bets"),("Observed Active Games",f"{int(m.games):,}","Games with activity")],ctx)
    daily=daily_ggr_by_game.run(ctx);daily["date"]=pd.to_datetime(daily.date)
    game=game_performance.run(ctx)
    if game.empty:
        empty_state("No casino activity matches these filters")
        return
    game["rtp_variance_meaning"] = game.rtp_variance.apply(lambda value: "Player-favourable · lower operator margin" if value > 0 else ("Operator-favourable · higher operator margin" if value < 0 else "In line with theoretical RTP"))
    c1,c2=st.columns([1.7,1],gap="medium")
    with c1:
        chart(polish(px.line(daily,x="date",y="casino_ggr",color="game_name",title="GGR TREND BY GAME"),390),daily,explanation="Observed daily GGR. Use the legend to isolate a game.")
    with c2:
        fig=px.scatter(game,x="Sessions",y="ggr_margin",size="GGR",color="game_name",text="game_name",title="POPULARITY VS PROFITABILITY");fig.update_traces(textposition="top center")
        chart(polish(fig,390,False),game,explanation="Bubble size is observed GGR; vertical position is observed GGR margin.")
    st.markdown("#### Game and table performance · SQL data mart")
    data_table(game,column_config={"GGR":st.column_config.NumberColumn(format="$%.0f"),"Bets":st.column_config.NumberColumn(format="$%.0f"),"Payout":st.column_config.NumberColumn(format="$%.0f"),"theoretical_rtp":st.column_config.NumberColumn("Theoretical RTP",format="%.2%%"),"actual_rtp":st.column_config.NumberColumn("Observed actual RTP",format="%.2%%"),"rtp_variance":st.column_config.NumberColumn("Observed RTP variance · actual − theoretical",format="%+.2%%"),"rtp_variance_meaning":st.column_config.TextColumn("Variance meaning"),"ggr_per_session":st.column_config.NumberColumn("Observed GGR / session",format="$%.2f"),"ggr_margin":st.column_config.NumberColumn("Observed GGR margin",format="%.2%%")})
    heat=sessions_heatmap.run(ctx)
    matrix=heat.pivot(index="day",columns="hour",values="sessions").reindex(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]).fillna(0)
    left,right=st.columns([2.5,1],gap="medium")
    with left:
        fig=go.Figure(go.Heatmap(z=matrix.to_numpy(),x=matrix.columns,y=matrix.index,colorscale=[[0,"#0a2730"],[.5,COLORS["gold"]],[1,COLORS["red"]]]));fig.update_layout(title="SESSIONS HEATMAP · SQL GROUP BY DAY × HOUR")
        chart(polish(fig,330,False),heat,explanation="Darker red indicates more observed sessions; it does not indicate worse performance.")
    with right:
        worst=game.loc[game.rtp_variance.abs().idxmax()]
        direction="players received more than theoretical; operator margin was lower" if worst.rtp_variance>0 else "players received less than theoretical; operator margin was higher"
        insight("Largest observed RTP variance",f"{worst.game_name}: {worst.rtp_variance*100:+.2f}pp (Actual − Theoretical); {direction}.","Review wager volume and sample size",True)
        insight("High-value opportunity","Strong GGR per session detected by SQL ranking.","Review capacity")
