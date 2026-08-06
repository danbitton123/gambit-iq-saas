from __future__ import annotations

"""Forecast-vs-actual backtest rows in the selected period, for every forecast target."""

SQL = """SELECT metric,forecast_date,actual_value,predicted_value,lower_bound,upper_bound,split
        FROM forecast_backtest WHERE forecast_date>=DATE(:start) AND forecast_date<DATE(:end) ORDER BY forecast_date"""


def run(ctx):
    return ctx.query(SQL)
