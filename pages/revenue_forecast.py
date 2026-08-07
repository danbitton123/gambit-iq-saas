from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from pages.overview_metrics import load
from ui.charts import polish
from ui.components import balanced_row_sizes, chart, money, pct
from ui.theme import page_header


def _forecast_card(label: str, value: str, note: str, tone: str = "neutral") -> None:
    st.markdown(
        f"<div class='forecast-card forecast-{tone}'><span>{label}</span>"
        f"<strong>{value}</strong><small>{note}</small></div>", unsafe_allow_html=True
    )


def render(ctx) -> None:
    page_header("REVENUE FORECAST", "Model-driven forward outlook and the gap to the run-rate target", "Executive Intelligence")

    metrics = load(ctx)

    st.markdown("### Forward outlook")
    st.caption("Model-driven revenue forecast and the gap to the run-rate target for the next 30 days. For accountable next actions, see AI Copilot → Recommendation center.")
    forecast_items = [
        ("Predicted GGR · 7 days", money(metrics.forecast_7), "Revenue forecast model", "positive"),
        ("Predicted GGR · 30 days", money(metrics.forecast_30), "Market-share adjusted" if ctx.country != "All markets" else "All-market model", "positive"),
        ("Predicted high churn", f"{int(metrics.risk_now.high_churn or 0):,}", f"{pct(metrics.risk_now.churn_rate)} average probability", "risk"),
        ("Predicted LTV Proxy · 90D", money(metrics.future_ltv), "Active players in scope", "neutral"),
        ("Forecast gap to target", money(metrics.forecast_gap), f"Target {money(metrics.run_rate_target_30)}", "positive" if metrics.forecast_gap >= 0 else "risk"),
    ]
    start = 0
    for size in balanced_row_sizes(len(forecast_items), max_per_row=3):
        row = forecast_items[start:start + size]
        start += size
        for col, item in zip(st.columns(len(row), gap="medium"), row):
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

    st.markdown("### Forecast by week")
    weekly = forecast.set_index("date").resample("W-MON", label="left", closed="left")[["forecast", "lower", "upper"]].sum().reset_index()
    weekly["week"] = weekly.date.dt.strftime("%d %b")
    weekly["low_error"] = weekly.forecast - weekly.lower
    weekly["high_error"] = weekly.upper - weekly.forecast
    fig = px.bar(weekly, x="week", y="forecast", title="PREDICTED GGR BY WEEK · WITH PREDICTION INTERVAL", color_discrete_sequence=[COLORS["gold"]])
    fig.update_traces(error_y=dict(type="data", symmetric=False, array=weekly.high_error, arrayminus=weekly.low_error, color=COLORS["cyan"]))
    chart(polish(fig, 320, False), weekly, explanation="30-day forecast grouped into calendar weeks; error bars show the 80% prediction interval.")
