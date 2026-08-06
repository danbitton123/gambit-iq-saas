from __future__ import annotations

"""Per-sport GGR, handle, bet count and hold — feeds the sport profitability bar chart."""

SQL = """SELECT sport,SUM(sportsbook_ggr) GGR,SUM(stake) Handle,COUNT(*) Bets,SUM(sportsbook_ggr)/NULLIF(SUM(stake),0) Hold FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY sport ORDER BY GGR"""


def run(ctx):
    return ctx.query(SQL)
