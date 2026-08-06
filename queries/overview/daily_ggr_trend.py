from __future__ import annotations

"""Daily observed total GGR — the solid line on the "Observed performance & 30-day forecast" chart."""

SQL = """SELECT metric_date date,SUM(total_ggr) ggr FROM mart_executive_daily
      WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
      AND (:country='All markets' OR country=:country) GROUP BY metric_date ORDER BY metric_date"""


def run(ctx):
    return ctx.query(SQL)
