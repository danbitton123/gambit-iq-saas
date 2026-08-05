from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from ui.charts import area_forecast, polish
from ui.components import chart, insight, kpis, money, period_delta
from ui.theme import page_header


def render(ctx) -> None:
    page_header("COMMAND CENTER", "Revenue, Risk & Player Intelligence", "Executive Overview")
    metric_sql = """
        WITH revenue AS (
          SELECT COALESCE(SUM(total_ggr),0) total_ggr FROM mart_executive_daily
          WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
            AND (:country='All markets' OR country=:country)
        ), activity AS (
          SELECT COUNT(DISTINCT a.player_id) active FROM int_player_activity_daily a
          JOIN dim_player p USING(player_id)
          WHERE activity_date>=DATE(:start) AND activity_date<DATE(:end)
            AND (:country='All markets' OR p.country=:country)
        ), scores AS (
          SELECT SUM(CASE WHEN churn_probability>=.70 THEN 1 ELSE 0 END) churn,
                 COALESCE(SUM(CASE WHEN fraud_risk>=.55 OR rg_risk>=.55 THEN MAX(lifetime_ggr,0) ELSE 0 END),0) protected
          FROM v_player_scores v WHERE (:country='All markets' OR country=:country)
            AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id
              AND s.session_start>=:start AND s.session_start<:end)
        )
        SELECT revenue.total_ggr, activity.active,
               scores.churn, scores.protected FROM revenue,activity,scores
    """
    metrics = ctx.query(metric_sql).iloc[0]
    previous = ctx.previous_query(metric_sql).iloc[0]
    kpis([
        ("Observed Total GGR", money(metrics.total_ggr), period_delta(metrics.total_ggr, previous.total_ggr)),
        ("Observed Active Players", f"{int(metrics.active):,}", period_delta(metrics.active, previous.active)),
        ("Predicted Churn-Risk Players", f"{int(metrics.churn):,}", "ML watchlist"),
        ("Estimated Risk Exposure", money(metrics.protected), "Active high-risk players"),
    ], ctx)
    daily = ctx.query("""
        SELECT metric_date date,SUM(total_ggr) value FROM mart_executive_daily
        WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
          AND (:country='All markets' OR country=:country)
        GROUP BY metric_date ORDER BY metric_date
    """)
    daily["date"] = pd.to_datetime(daily["date"])
    history = daily.tail(60)
    forecast=ctx.query("SELECT forecast_date date,predicted_revenue value,lower_bound lower,upper_bound upper FROM revenue_forecast ORDER BY forecast_date");forecast["date"]=pd.to_datetime(forecast.date)
    left, right = st.columns([3.3, 1])
    with left:
        chart(area_forecast(history, forecast, title="GGR HISTORY & 30-DAY FORECAST"), history,
              explanation="Observed casino and sportsbook GGR for the selected filters; the dotted series is the model forecast for all markets.")
    with right:
        st.markdown("<p class='panel-title'>Rule-based Priority Feed</p>", unsafe_allow_html=True)
        insight("Churn review", "Active players above the 70% churn threshold.", f"{int(metrics.churn):,} players")
        insight("Risk review", "Estimated lifetime GGR attached to active fraud or RG flags.", money(metrics.protected), True)
        st.caption("Priorities are calculated from the filtered SQL snapshot; they are decision support, not automated actions.")

    sample = ctx.query("""
        SELECT player_id, churn_probability, predicted_ltv_90d, session_count,
          CASE WHEN churn_probability<.4 THEN 'Stable' WHEN churn_probability<.7 THEN 'Watch' ELSE 'High risk' END risk_band
        FROM v_player_scores v WHERE (:country='All markets' OR country=:country)
          AND EXISTS (SELECT 1 FROM v_sessions_enriched s WHERE s.player_id=v.player_id AND s.session_start>=:start AND s.session_start<:end)
        ORDER BY player_id LIMIT 1200
    """)
    game = ctx.query("""
        SELECT game_name, SUM(casino_ggr) GGR, COUNT(*) Sessions FROM v_sessions_enriched
        WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country)
        GROUP BY game_name ORDER BY GGR
    """)
    risk = ctx.query("""
        SELECT 'Churn risk' Dimension,
          SUM(churn_probability<.25) Low, SUM(churn_probability>=.25 AND churn_probability<.5) Moderate,
          SUM(churn_probability>=.5 AND churn_probability<.75) High, SUM(churn_probability>=.75) Critical
        FROM v_player_scores WHERE (:country='All markets' OR country=:country)
        UNION ALL SELECT 'Fraud risk', SUM(fraud_risk<.25), SUM(fraud_risk>=.25 AND fraud_risk<.5), SUM(fraud_risk>=.5 AND fraud_risk<.75), SUM(fraud_risk>=.75)
        FROM v_player_scores WHERE (:country='All markets' OR country=:country)
        UNION ALL SELECT 'RG risk', SUM(rg_risk<.25), SUM(rg_risk>=.25 AND rg_risk<.5), SUM(rg_risk>=.5 AND rg_risk<.75), SUM(rg_risk>=.75)
        FROM v_player_scores WHERE (:country='All markets' OR country=:country)
    """)
    c1,c2,c3=st.columns([1.2,1.2,1])
    with c1:
        fig=px.scatter(sample,x="churn_probability",y="predicted_ltv_90d",color="risk_band",size="session_count",title="PLAYER VALUE VS CHURN RISK",color_discrete_map={"Stable":COLORS["green"],"Watch":COLORS["gold"],"High risk":COLORS["red"]})
        chart(polish(fig,340), sample, explanation="Bubble size represents observed session count; colors consistently progress from green to amber to red as risk increases.")
    with c2:
        fig=px.bar(game,x="GGR",y="game_name",orientation="h",color="GGR",title="GAME PERFORMANCE RANKING",color_continuous_scale=[COLORS["emerald"],COLORS["green"]]);fig.update_layout(coloraxis_showscale=False)
        chart(polish(fig,340,False), game, explanation="Observed GGR by game for the selected period and market.")
    with c3:
        fig=go.Figure(go.Heatmap(z=risk[["Low","Moderate","High","Critical"]].to_numpy(),x=["Low","Moderate","High","Critical"],y=risk.Dimension,colorscale=[[0,COLORS["green"]],[.5,COLORS["gold"]],[1,COLORS["red"]]],text=risk[["Low","Moderate","High","Critical"]].to_numpy(),texttemplate="%{text}"));fig.update_layout(title="RISK MONITORING HEATMAP")
        chart(polish(fig,340,False), risk, explanation="Risk bands use the same green–amber–red severity scale used throughout Gambit IQ.")
