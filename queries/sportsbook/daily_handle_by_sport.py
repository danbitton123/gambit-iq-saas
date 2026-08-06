from __future__ import annotations

"""Daily settled handle (exposure) and GGR per sport — feeds the daily handle line chart."""

SQL = """SELECT DATE(bet_date) date,sport,SUM(stake) Exposure,SUM(sportsbook_ggr) GGR FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY DATE(bet_date),sport ORDER BY date"""


def run(ctx):
    return ctx.query(SQL)
