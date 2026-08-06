from __future__ import annotations

"""The acquisition channel with the lowest predicted 90-day ROAS proxy — feeds the "Acquisition efficiency" alert."""

COST_SQL = "CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END"

SQL = f"""SELECT p.channel,COUNT(*) players,SUM({COST_SQL}) cost,
      SUM(v.predicted_ltv_90d) predicted_value,SUM(v.predicted_ltv_90d)/NULLIF(SUM({COST_SQL}),0) roas
      FROM players p JOIN v_player_scores v USING(player_id)
      WHERE p.registration_date>=:start AND p.registration_date<:end
      AND (:country='All markets' OR p.country=:country) GROUP BY p.channel ORDER BY roas LIMIT 1"""


def run(ctx):
    return ctx.query(SQL)
