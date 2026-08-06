from __future__ import annotations

"""Average daily settled handle over the filtered period — the dashed reference line on the handle chart."""

SQL = """WITH d AS (SELECT DATE(bet_date),SUM(stake) x FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY DATE(bet_date)) SELECT AVG(x) FROM d"""


def run(ctx):
    return ctx.scalar(SQL) or 0
