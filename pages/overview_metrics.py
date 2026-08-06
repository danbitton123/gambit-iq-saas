from __future__ import annotations

import math
from types import SimpleNamespace

import pandas as pd

from queries.overview import (
    daily_ggr_trend, market_share, payment_approval, performance_summary,
    revenue_forecast, risk_bands, risk_summary, sportsbook_concentration,
    worst_channel_roas, worst_rtp_variance,
)


def num(value, default: float = 0.0) -> float:
    return default if value is None or pd.isna(value) else float(value)


def change(current: float, previous: float) -> float | None:
    return None if math.isclose(previous, 0.0, abs_tol=1e-12) else (current - previous) / abs(previous)


def load(ctx) -> SimpleNamespace:
    """Every derived value behind the Command Center and Forecast & Recommendations pages,
    computed once so both pages agree exactly on the same underlying SQL-sourced numbers."""
    current = performance_summary.run(ctx)
    previous = performance_summary.run_previous(ctx)
    days = max((ctx.end.normalize() - ctx.start.normalize()).days + 1, 1)

    hold = num(current.ggr) / num(current.wagers) if num(current.wagers) else 0
    previous_hold = num(previous.ggr) / num(previous.wagers) if num(previous.wagers) else 0

    risk_now = risk_summary.run(ctx)
    risk_previous = risk_summary.run_previous(ctx)
    churn_change = num(risk_now.churn_rate) - num(risk_previous.churn_rate)

    game = worst_rtp_variance.run(ctx)
    game_row = game.iloc[0] if not game.empty else None
    rtp_variance = abs(num(game_row.variance)) if game_row is not None else 0

    campaign = worst_channel_roas.run(ctx)
    campaign_row = campaign.iloc[0] if not campaign.empty else None
    worst_roas = num(campaign_row.roas) if campaign_row is not None else 0

    payment = payment_approval.run(ctx)
    previous_payment = payment_approval.run_previous(ctx)
    approval_drop = max(num(previous_payment.approval) - num(payment.approval), 0)

    sportsbook = sportsbook_concentration.run(ctx)
    sportsbook_row = sportsbook.iloc[0] if not sportsbook.empty else None
    event_share = num(sportsbook_row.share) if sportsbook_row is not None else 0
    revenue_change = change(num(current.ggr), num(previous.ggr)) or 0

    daily = daily_ggr_trend.run(ctx)
    daily["date"] = pd.to_datetime(daily.date)
    forecast = revenue_forecast.run(ctx)
    forecast["date"] = pd.to_datetime(forecast.date)
    if ctx.country != "All markets":
        forecast[["forecast", "lower", "upper"]] *= market_share.run(ctx)
    forecast_7 = forecast.head(7).forecast.sum()
    forecast_30 = forecast.head(30).forecast.sum()
    run_rate_target_30 = max(num(current.ggr) / days * 30 * 1.05, 0)
    forecast_gap = forecast_30 - run_rate_target_30
    revenue_at_risk = num(risk_now.value_at_risk)
    future_ltv = num(risk_now.future_ltv)

    bands = risk_bands.run(ctx)

    return SimpleNamespace(
        current=current, previous=previous, days=days, hold=hold, previous_hold=previous_hold,
        risk_now=risk_now, risk_previous=risk_previous, churn_change=churn_change,
        game_row=game_row, rtp_variance=rtp_variance, campaign_row=campaign_row, worst_roas=worst_roas,
        payment=payment, previous_payment=previous_payment, approval_drop=approval_drop,
        sportsbook_row=sportsbook_row, event_share=event_share, revenue_change=revenue_change,
        daily=daily, forecast=forecast, forecast_7=forecast_7, forecast_30=forecast_30,
        run_rate_target_30=run_rate_target_30, forecast_gap=forecast_gap,
        revenue_at_risk=revenue_at_risk, future_ltv=future_ltv, bands=bands,
    )
