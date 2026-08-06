from __future__ import annotations

"""Daily observed casino GGR, split by game — feeds the GGR trend line chart."""

SQL = """SELECT metric_date date,game_name,SUM(ggr) casino_ggr FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY metric_date,game_name ORDER BY metric_date"""


def run(ctx):
    return ctx.query(SQL)
