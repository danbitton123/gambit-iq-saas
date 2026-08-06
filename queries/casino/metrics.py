from __future__ import annotations

"""Observed Casino GGR, Total Bets, GGR Margin, Actual RTP and Active Games."""

SQL = """SELECT COALESCE(SUM(bets),0) bets,COALESCE(SUM(payouts),0) payout,COALESCE(SUM(ggr),0) ggr,COUNT(DISTINCT game_id) games FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country)"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
