from __future__ import annotations

"""Total settled casino + sportsbook bets and payouts — the base for the GGR waterfall."""

SQL = """SELECT COALESCE(SUM(bets),0) bets,COALESCE(SUM(payout),0) payout FROM (SELECT SUM(total_bet_amount) bets,SUM(total_payout_amount) payout FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) UNION ALL SELECT SUM(stake),SUM(payout) FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country))"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
