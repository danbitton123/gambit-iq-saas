from __future__ import annotations

"""Single event with the largest settled handle — the real figure behind the "Concentrated liability" card."""

SQL = """SELECT event_name,SUM(stake) exposure FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name ORDER BY exposure DESC LIMIT 1"""


def run(ctx):
    return ctx.query(SQL)
