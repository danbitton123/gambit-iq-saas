from __future__ import annotations

"""Predicted daily GGR with its 80% prediction interval, for the 7/30-day forward outlook."""

SQL = """SELECT forecast_date date,predicted_revenue forecast,lower_bound lower,upper_bound upper
      FROM revenue_forecast ORDER BY forecast_date"""


def run(ctx):
    return ctx.query(SQL)
