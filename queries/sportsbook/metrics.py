from __future__ import annotations

"""Observed Sportsbook GGR, Handle, Hold, Realized Downside and Live Bets."""

SQL = """SELECT COALESCE(SUM(stake),0) handle,COALESCE(SUM(payout),0) payout,COALESCE(SUM(sportsbook_ggr),0) ggr,COALESCE(SUM(is_live),0) live,COALESCE(SUM(CASE WHEN sportsbook_ggr<0 THEN -sportsbook_ggr ELSE 0 END),0) exposure FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country)"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
