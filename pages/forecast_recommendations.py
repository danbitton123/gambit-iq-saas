from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from pages.overview_metrics import load, num
from ui.charts import polish
from ui.components import chart, money, pct
from ui.theme import page_header


def _forecast_card(label: str, value: str, note: str, tone: str = "neutral") -> None:
    st.markdown(
        f"<div class='forecast-card forecast-{tone}'><span>{label}</span>"
        f"<strong>{value}</strong><small>{note}</small></div>", unsafe_allow_html=True
    )


def _recommendation(title: str, what: str, why: str, impact: str, action: str, confidence: float) -> None:
    level = "High" if confidence >= .8 else "Medium" if confidence >= .65 else "Low"
    st.markdown(
        f"<article class='recommendation-card'><div class='recommendation-head'><strong>{title}</strong>"
        f"<span>{level} confidence · {confidence:.0%}</span></div>"
        f"<div class='recommendation-grid'><div><small>WHAT IS HAPPENING?</small><p>{what}</p></div>"
        f"<div><small>WHY?</small><p>{why}</p></div><div><small>ESTIMATED IMPACT</small><p>{impact}</p></div>"
        f"<div><small>RECOMMENDED ACTION</small><p>{action}</p></div></div></article>",
        unsafe_allow_html=True,
    )


def render(ctx) -> None:
    page_header("FORECAST & RECOMMENDATIONS", "Forward outlook, forecast model and accountable decision support", "Executive Intelligence")

    metrics = load(ctx)
    current = metrics.current
    game_row, campaign_row, sportsbook_row, payment = metrics.game_row, metrics.campaign_row, metrics.sportsbook_row, metrics.payment

    st.markdown("### Forward outlook")
    st.caption("Model-driven revenue forecast and the gap to the run-rate target for the next 30 days.")
    forecast_cols = st.columns(5)
    forecast_items = [
        ("Predicted GGR · 7 days", money(metrics.forecast_7), "Revenue forecast model", "positive"),
        ("Predicted GGR · 30 days", money(metrics.forecast_30), "Market-share adjusted" if ctx.country != "All markets" else "All-market model", "positive"),
        ("Predicted high churn", f"{int(metrics.risk_now.high_churn or 0):,}", f"{pct(metrics.risk_now.churn_rate)} average probability", "risk"),
        ("Predicted LTV Proxy · 90D", money(metrics.future_ltv), "Active players in scope", "neutral"),
        ("Forecast gap to target", money(metrics.forecast_gap), f"Target {money(metrics.run_rate_target_30)}", "positive" if metrics.forecast_gap >= 0 else "risk"),
    ]
    for col, item in zip(forecast_cols, forecast_items):
        with col:
            _forecast_card(*item)

    daily, forecast = metrics.daily, metrics.forecast
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily.date, y=daily.ggr, name="Observed GGR", line=dict(color=COLORS["cyan"], width=2.5)))
    fig.add_trace(go.Scatter(x=forecast.date, y=forecast.upper, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=forecast.date, y=forecast.lower, fill="tonexty", fillcolor="rgba(38,198,229,.13)", line=dict(width=0), name="Prediction interval"))
    fig.add_trace(go.Scatter(x=forecast.date, y=forecast.forecast, name="Predicted GGR", line=dict(color=COLORS["gold"], width=2.5, dash="dot")))
    fig.add_hline(y=metrics.run_rate_target_30/30 if metrics.run_rate_target_30 else 0, line_dash="dash", line_color=COLORS["green"], annotation_text="Daily objective")
    fig.update_layout(title="OBSERVED PERFORMANCE & 30-DAY FORECAST")
    chart(polish(fig, 390), explanation="Observed filtered GGR followed by the model forecast and prediction interval. Country views use the market's recent observed GGR share.")

    st.markdown("### Recommended decisions")
    st.caption("Decision support only. Every recommendation explains the signal, cause, impact, action and model confidence; execution remains human-approved.")
    recommendation_cols = st.columns(2)
    recommendations = [
        ("Protect high-value players", f"Predicted churn risk is elevated for {int(metrics.risk_now.high_churn or 0):,} active players.", "The churn model detects lower recent activity and weaker engagement patterns.", f"Up to {money(metrics.revenue_at_risk)} of predicted 90-day LTV Proxy is attached to the high-risk group.", f"Launch a targeted retention journey for {int(metrics.risk_now.high_churn or 0):,} players, excluding fraud and RG flags.", num(metrics.risk_now.confidence, .68)),
        ("Correct the largest RTP deviation", f"{game_row.game_name if game_row is not None else 'The leading game'} differs from theoretical RTP by {metrics.rtp_variance:.2%}.", "Observed payouts diverge from the configured theoretical return; sample size and feed quality may contribute.", f"{money(num(game_row.bets) if game_row is not None else 0)} of observed bets require validation.", "Confirm game configuration, provider settlement data and statistical significance before escalation.", .88 if game_row is not None and num(game_row.bets) > 10000 else .70),
        ("Improve acquisition allocation", f"{campaign_row.channel if campaign_row is not None else 'The weakest channel'} has the lowest predicted ROAS proxy at {metrics.worst_roas:.2f}x.", "Predicted 90-day LTV Proxy is low relative to the channel cost assumption.", f"Review {int(campaign_row.players if campaign_row is not None else 0):,} acquired players before the next budget cycle.", "Validate actual media spend, then reduce or redesign the weakest cohort while protecting high-quality sources.", num(metrics.risk_now.confidence, .68)),
        ("Reduce operational exposure", f"Deposit approvals declined {metrics.approval_drop:.1%}; the largest sportsbook event represents {metrics.event_share:.1%} of handle.", "Payment friction and concentrated settled handle can increase liquidity and trading volatility.", f"Current approved deposits total {money(current.deposits)}; concentrated event handle is {money(sportsbook_row.handle if sportsbook_row is not None else 0)}.", "Review payment-method declines and event limits in parallel; escalate only breaches above approved thresholds.", .82),
    ]
    for index, args in enumerate(recommendations):
        with recommendation_cols[index % 2]:
            _recommendation(*args)
