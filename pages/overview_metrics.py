from __future__ import annotations

import math
from types import SimpleNamespace

import pandas as pd

from queries.overview import daily_ggr_trend, market_share, performance_summary, revenue_forecast, risk_bands, risk_summary


def num(value, default: float = 0.0) -> float:
    return default if value is None or pd.isna(value) else float(value)


def change(current: float, previous: float) -> float | None:
    return None if math.isclose(previous, 0.0, abs_tol=1e-12) else (current - previous) / abs(previous)


def load(ctx) -> SimpleNamespace:
    """Every derived value behind the Command Center and Revenue Forecast pages, computed once
    so both pages agree exactly on the same underlying SQL-sourced numbers."""
    current = performance_summary.run(ctx)
    previous = performance_summary.run_previous(ctx)
    days = max((ctx.end.normalize() - ctx.start.normalize()).days + 1, 1)

    hold = num(current.ggr) / num(current.wagers) if num(current.wagers) else 0
    previous_hold = num(previous.ggr) / num(previous.wagers) if num(previous.wagers) else 0

    risk_now = risk_summary.run(ctx)
    future_ltv = num(risk_now.future_ltv)

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

    bands = risk_bands.run(ctx)

    return SimpleNamespace(
        current=current, previous=previous, days=days, hold=hold, previous_hold=previous_hold,
        risk_now=risk_now, future_ltv=future_ltv,
        daily=daily, forecast=forecast, forecast_7=forecast_7, forecast_30=forecast_30,
        run_rate_target_30=run_rate_target_30, forecast_gap=forecast_gap, bands=bands,
    )
