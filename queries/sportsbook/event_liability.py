from __future__ import annotations

"""Per-event settled exposure, GGR and bet count with a HIGH/MEDIUM/LOW concentration flag."""

SQL = """WITH e AS (SELECT event_name,sport,SUM(stake) Exposure,SUM(sportsbook_ggr) GGR,COUNT(*) Bets FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end AND (:country='All markets' OR country=:country) GROUP BY event_name,sport), q AS (SELECT AVG(Exposure) avg_exp FROM e) SELECT e.*,CASE WHEN Exposure>avg_exp*1.5 THEN 'HIGH' WHEN Exposure>avg_exp THEN 'MEDIUM' ELSE 'LOW' END Status FROM e CROSS JOIN q ORDER BY Exposure DESC"""


def run(ctx):
    return ctx.query(SQL)
