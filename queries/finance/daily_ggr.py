from __future__ import annotations

"""Daily observed total GGR — feeds the revenue trend line chart."""

SQL = """SELECT metric_date date,SUM(total_ggr) GGR FROM mart_executive_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY metric_date ORDER BY metric_date"""


def run(ctx):
    return ctx.query(SQL)
