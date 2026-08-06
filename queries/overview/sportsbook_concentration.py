from __future__ import annotations

"""The sportsbook event holding the largest share of settled handle — feeds the "Sportsbook concentration" alert."""

SQL = """WITH events AS (SELECT event_name,SUM(stake) handle FROM v_sports_bets_enriched
      WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name)
      SELECT event_name,handle,handle/(SELECT NULLIF(SUM(handle),0) FROM events) share FROM events ORDER BY handle DESC LIMIT 1"""


def run(ctx):
    return ctx.query(SQL)
