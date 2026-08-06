from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from queries.overview import (
    daily_ggr_trend, market_share, payment_approval, performance_summary,
    revenue_forecast, risk_bands, risk_summary, sportsbook_concentration,
    worst_channel_roas, worst_rtp_variance,
)
from ui.charts import polish
from ui.components import chart, money, pct, period_delta
from ui.kpi_governance import kpi_help
from ui.theme import page_header


def _num(value, default: float = 0.0) -> float:
    return default if value is None or pd.isna(value) else float(value)


def _change(current: float, previous: float) -> float | None:
    return None if math.isclose(previous, 0.0, abs_tol=1e-12) else (current - previous) / abs(previous)


def _severity(value: float, warning: float, critical: float) -> str:
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "stable"


def _executive_kpis(items: list[dict], ctx) -> None:
    cols = st.columns(len(items))
    for index, item in enumerate(items):
        with cols[index]:
            st.metric(
                item["label"], item["value"], item["delta"],
                delta_color=item.get("delta_color", "normal"),
                help=kpi_help(item["label"], ctx.period_label, ctx.last_updated_label()),
            )
            progress = min(max(float(item["progress"]), 0.0), 1.0)
            st.progress(progress)
            st.caption(f"{progress:.0%} of objective · {item['objective']}")


def _alert_card(title: str, detail: str, value: str, severity: str, action: str) -> None:
    labels = {"critical": "CRITICAL", "warning": "REVIEW", "stable": "STABLE"}
    st.markdown(
        f"<article class='command-alert command-alert-{severity}'>"
        f"<div class='command-alert-top'><span>{labels[severity]}</span><strong>{title}</strong></div>"
        f"<div class='command-alert-value'>{value}</div><p>{detail}</p><small>{action}</small></article>",
        unsafe_allow_html=True,
    )


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
    page_header("COMMAND CENTER", "Performance, priorities, forecasts and decisions in one governed view", "Executive Intelligence")

    current = performance_summary.run(ctx)
    previous = performance_summary.run_previous(ctx)
    days = max((ctx.end.normalize() - ctx.start.normalize()).days + 1, 1)

    targets = {
        "ggr": _num(previous.ggr) * 1.05 if _num(previous.ggr) > 0 else max(_num(current.ggr), 1),
        "ngr": _num(previous.ngr) * 1.05 if _num(previous.ngr) > 0 else max(_num(current.ngr), 1),
        "players": _num(previous.players) * 1.03 if _num(previous.players) > 0 else max(_num(current.players), 1),
        "deposits": _num(previous.deposits) * 1.05 if _num(previous.deposits) > 0 else max(_num(current.deposits), 1),
        "ftd": _num(previous.ftd) * 1.05 if _num(previous.ftd) > 0 else max(_num(current.ftd), 1),
        "hold": .07,
    }
    hold = _num(current.ggr) / _num(current.wagers) if _num(current.wagers) else 0
    previous_hold = _num(previous.ggr) / _num(previous.wagers) if _num(previous.wagers) else 0

    st.markdown("### Performance at a glance")
    st.caption("Observed results, period-over-period movement and management objectives. Objectives use the prior period +5% (+3% for active players); blended hold objective is 7%.")
    _executive_kpis([
        {"label": "Observed Total GGR", "value": money(current.ggr), "delta": period_delta(current.ggr, previous.ggr), "progress": _num(current.ggr)/targets["ggr"], "objective": money(targets["ggr"])},
        {"label": "Estimated NGR", "value": money(current.ngr), "delta": period_delta(current.ngr, previous.ngr), "progress": _num(current.ngr)/targets["ngr"], "objective": money(targets["ngr"])},
        {"label": "Observed Active Players", "value": f"{int(current.players or 0):,}", "delta": period_delta(current.players, previous.players), "progress": _num(current.players)/targets["players"], "objective": f"{targets['players']:,.0f}"},
        {"label": "Observed Deposits", "value": money(current.deposits), "delta": period_delta(current.deposits, previous.deposits), "progress": _num(current.deposits)/targets["deposits"], "objective": money(targets["deposits"])},
        {"label": "Observed FTD", "value": f"{int(current.ftd or 0):,}", "delta": period_delta(current.ftd, previous.ftd), "progress": _num(current.ftd)/targets["ftd"], "objective": f"{targets['ftd']:,.0f}"},
        {"label": "Observed Blended Hold", "value": pct(hold, 2), "delta": period_delta(hold, previous_hold), "progress": hold/targets["hold"], "objective": "7.0% hold"},
    ], ctx)

    risk_now = risk_summary.run(ctx)
    risk_previous = risk_summary.run_previous(ctx)
    churn_change = (_num(risk_now.churn_rate) - _num(risk_previous.churn_rate))

    game = worst_rtp_variance.run(ctx)
    game_row = game.iloc[0] if not game.empty else None
    rtp_variance = abs(_num(game_row.variance)) if game_row is not None else 0

    campaign = worst_channel_roas.run(ctx)
    campaign_row = campaign.iloc[0] if not campaign.empty else None
    worst_roas = _num(campaign_row.roas) if campaign_row is not None else 0

    payment = payment_approval.run(ctx)
    previous_payment = payment_approval.run_previous(ctx)
    approval_drop = max(_num(previous_payment.approval) - _num(payment.approval), 0)

    sportsbook = sportsbook_concentration.run(ctx)
    sportsbook_row = sportsbook.iloc[0] if not sportsbook.empty else None
    event_share = _num(sportsbook_row.share) if sportsbook_row is not None else 0
    revenue_change = _change(_num(current.ggr), _num(previous.ggr)) or 0

    st.markdown("### Action required")
    alert_cols = st.columns(3)
    alerts = [
        ("Revenue momentum", "GGR versus the immediately preceding equivalent period.", f"{revenue_change:+.1%}", _severity(max(-revenue_change, 0), .05, .12), "Review the revenue mix and largest negative contributors."),
        ("Casino RTP anomaly", f"{game_row.game_name if game_row is not None else 'No game'} has the largest absolute variance from theoretical RTP.", f"{rtp_variance:+.2%} abs. variance", _severity(rtp_variance, .02, .04), "Validate sample size, game configuration and provider feed."),
        ("Acquisition efficiency", f"{campaign_row.channel if campaign_row is not None else 'No channel'} is the weakest predicted 90-day ROAS proxy.", f"{worst_roas:.2f}x ROAS proxy", "critical" if worst_roas and worst_roas < 1 else "warning" if worst_roas < 2 else "stable", "Review spend assumptions before reallocating budget."),
        ("Predicted churn", "Average churn probability among players active in the selected scope.", f"{churn_change:+.1%} vs prior", _severity(max(churn_change, 0), .03, .08), f"Prioritize {int(risk_now.high_churn or 0):,} high-risk players."),
        ("Payment risk", "Change in observed deposit approval rate versus the previous period.", f"{approval_drop:.1%} approval decline", _severity(approval_drop, .02, .05), "Inspect declines by payment method and issuer."),
        ("Sportsbook concentration", f"{sportsbook_row.event_name if sportsbook_row is not None else 'No event'} holds the largest share of settled handle.", f"{event_share:.1%} of handle", _severity(event_share, .30, .45), "Review event-level concentration and trading limits."),
    ]
    for index, args in enumerate(alerts):
        with alert_cols[index % 3]:
            _alert_card(*args)

    daily = daily_ggr_trend.run(ctx)
    daily["date"] = pd.to_datetime(daily.date)
    forecast = revenue_forecast.run(ctx)
    forecast["date"] = pd.to_datetime(forecast.date)
    if ctx.country != "All markets":
        forecast[["forecast", "lower", "upper"]] *= market_share.run(ctx)
    forecast_7 = forecast.head(7).forecast.sum()
    forecast_30 = forecast.head(30).forecast.sum()
    run_rate_target_30 = max(_num(current.ggr) / days * 30 * 1.05, 0)
    forecast_gap = forecast_30 - run_rate_target_30
    revenue_at_risk = _num(risk_now.value_at_risk)
    future_ltv = _num(risk_now.future_ltv)

    st.markdown("### Forward outlook")
    forecast_cols = st.columns(5)
    forecast_items = [
        ("Predicted GGR · 7 days", money(forecast_7), "Revenue forecast model", "positive"),
        ("Predicted GGR · 30 days", money(forecast_30), "Market-share adjusted" if ctx.country != "All markets" else "All-market model", "positive"),
        ("Predicted high churn", f"{int(risk_now.high_churn or 0):,}", f"{pct(risk_now.churn_rate)} average probability", "risk"),
        ("Predicted LTV Proxy · 90D", money(future_ltv), "Active players in scope", "neutral"),
        ("Forecast gap to target", money(forecast_gap), f"Target {money(run_rate_target_30)}", "positive" if forecast_gap >= 0 else "risk"),
    ]
    for col, item in zip(forecast_cols, forecast_items):
        with col:
            _forecast_card(*item)

    left, right = st.columns([1.65, 1])
    with left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily.date, y=daily.ggr, name="Observed GGR", line=dict(color=COLORS["cyan"], width=2.5)))
        fig.add_trace(go.Scatter(x=forecast.date, y=forecast.upper, line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=forecast.date, y=forecast.lower, fill="tonexty", fillcolor="rgba(38,198,229,.13)", line=dict(width=0), name="Prediction interval"))
        fig.add_trace(go.Scatter(x=forecast.date, y=forecast.forecast, name="Predicted GGR", line=dict(color=COLORS["gold"], width=2.5, dash="dot")))
        fig.add_hline(y=run_rate_target_30/30 if run_rate_target_30 else 0, line_dash="dash", line_color=COLORS["green"], annotation_text="Daily objective")
        fig.update_layout(title="OBSERVED PERFORMANCE & 30-DAY FORECAST")
        chart(polish(fig, 390), explanation="Observed filtered GGR followed by the model forecast and prediction interval. Country views use the market's recent observed GGR share.")
    with right:
        bands = risk_bands.run(ctx)
        color_map = {"Stable": COLORS["green"], "Watch": COLORS["gold"], "High risk": COLORS["red"]}
        fig = px.bar(bands, x="segment", y="ltv_proxy", color="segment", text="players", title="LTV PROXY AT RISK BY CHURN BAND", color_discrete_map=color_map)
        fig.update_traces(texttemplate="%{text:,} players", textposition="outside")
        chart(polish(fig, 390, False), bands, explanation="Predicted 90-day LTV Proxy of active players, segmented by predicted churn probability.")

    st.markdown("### Recommended decisions")
    st.caption("Decision support only. Every recommendation explains the signal, cause, impact, action and model confidence; execution remains human-approved.")
    recommendation_cols = st.columns(2)
    recommendations = [
        ("Protect high-value players", f"Predicted churn risk is elevated for {int(risk_now.high_churn or 0):,} active players.", "The churn model detects lower recent activity and weaker engagement patterns.", f"Up to {money(revenue_at_risk)} of predicted 90-day LTV Proxy is attached to the high-risk group.", f"Launch a targeted retention journey for {int(risk_now.high_churn or 0):,} players, excluding fraud and RG flags.", _num(risk_now.confidence, .68)),
        ("Correct the largest RTP deviation", f"{game_row.game_name if game_row is not None else 'The leading game'} differs from theoretical RTP by {rtp_variance:.2%}.", "Observed payouts diverge from the configured theoretical return; sample size and feed quality may contribute.", f"{money(_num(game_row.bets) if game_row is not None else 0)} of observed bets require validation.", "Confirm game configuration, provider settlement data and statistical significance before escalation.", .88 if game_row is not None and _num(game_row.bets) > 10000 else .70),
        ("Improve acquisition allocation", f"{campaign_row.channel if campaign_row is not None else 'The weakest channel'} has the lowest predicted ROAS proxy at {worst_roas:.2f}x.", "Predicted 90-day LTV Proxy is low relative to the channel cost assumption.", f"Review {int(campaign_row.players if campaign_row is not None else 0):,} acquired players before the next budget cycle.", "Validate actual media spend, then reduce or redesign the weakest cohort while protecting high-quality sources.", _num(risk_now.confidence, .68)),
        ("Reduce operational exposure", f"Deposit approvals declined {approval_drop:.1%}; the largest sportsbook event represents {event_share:.1%} of handle.", "Payment friction and concentrated settled handle can increase liquidity and trading volatility.", f"Current approved deposits total {money(current.deposits)}; concentrated event handle is {money(sportsbook_row.handle if sportsbook_row is not None else 0)}.", "Review payment-method declines and event limits in parallel; escalate only breaches above approved thresholds.", .82),
    ]
    for index, args in enumerate(recommendations):
        with recommendation_cols[index % 2]:
            _recommendation(*args)
