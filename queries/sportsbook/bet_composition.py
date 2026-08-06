from __future__ import annotations

"""Settled handle split between live and pre-match bets — feeds the betting composition pie chart."""

SQL = """SELECT CASE is_live WHEN 1 THEN 'Live' ELSE 'Pre-match' END Type,SUM(stake) stake FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY is_live"""


def run(ctx):
    return ctx.query(SQL)
