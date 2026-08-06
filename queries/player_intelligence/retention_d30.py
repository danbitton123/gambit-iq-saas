from __future__ import annotations

"""Observed Retention D30: activated players (mature 37-day window) returning on days 30-36."""

SQL = """
WITH activity AS (
  SELECT player_id,DATE(session_start) activity_date FROM sessions
  UNION
  SELECT player_id,DATE(bet_date) FROM sports_bets
), first_activity AS (
  SELECT player_id,MIN(activity_date) activation_date FROM activity GROUP BY player_id
), eligible AS (
  SELECT f.player_id,f.activation_date
  FROM first_activity f JOIN players p USING(player_id)
  WHERE f.activation_date>=DATE(:start) AND f.activation_date<DATE(:end)
    AND f.activation_date<=DATE(:end,'-37 days')
    AND (:country='All markets' OR p.country=:country)
), retained AS (
  SELECT DISTINCT e.player_id
  FROM eligible e JOIN activity a USING(player_id)
  WHERE a.activity_date>=DATE(e.activation_date,'+30 days')
    AND a.activity_date<DATE(e.activation_date,'+37 days')
)
SELECT COUNT(*) eligible_players,COUNT(r.player_id) retained_players,
       1.0*COUNT(r.player_id)/NULLIF(COUNT(*),0) retention_d30
FROM eligible e LEFT JOIN retained r USING(player_id)
"""


def run(ctx):
    return ctx.query(SQL).iloc[0]
