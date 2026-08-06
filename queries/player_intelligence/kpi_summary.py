from __future__ import annotations

"""Every KPI card on Player 360 computed in one SQL pass instead of pandas aggregation over
player_base, to keep "every dashboard KPI is calculated in SQL" true for this page too. Filter
semantics mirror the page's previous pandas logic exactly (same date windows, same player
universe) so displayed numbers are unchanged."""

SQL = """
WITH current_casino AS (
  SELECT player_id,COUNT(*) sessions FROM v_sessions_enriched
  WHERE session_start>=:start AND session_start<:end GROUP BY player_id
), current_sports AS (
  SELECT player_id,COUNT(*) sports_bets FROM v_sports_bets_enriched
  WHERE bet_date>=:start AND bet_date<:end GROUP BY player_id
), previous_casino AS (
  SELECT player_id,COUNT(*) sessions FROM v_sessions_enriched
  WHERE session_start>=:prev_start AND session_start<:prev_end GROUP BY player_id
), previous_sports AS (
  SELECT player_id,COUNT(*) sports_bets FROM v_sports_bets_enriched
  WHERE bet_date>=:prev_start AND bet_date<:prev_end GROUP BY player_id
), lifetime AS (
  SELECT player_id,SUM(ggr) lifetime_ggr FROM (
    SELECT player_id,SUM(casino_ggr) ggr FROM sessions GROUP BY player_id
    UNION ALL SELECT player_id,SUM(sportsbook_ggr) FROM sports_bets GROUP BY player_id
  ) GROUP BY player_id
), base AS (
  SELECT v.player_id,v.churn_probability,v.remaining_ltv_90d,v.rg_risk,
    COALESCE(cc.sessions,0) casino_sessions,
    COALESCE(cc.sessions,0)+COALESCE(cs.sports_bets,0) activity,
    COALESCE(pc.sessions,0)+COALESCE(ps.sports_bets,0) previous_activity,
    COALESCE(l.lifetime_ggr,0) lifetime_ggr
  FROM v_player_scores v
  LEFT JOIN current_casino cc USING(player_id) LEFT JOIN current_sports cs USING(player_id)
  LEFT JOIN previous_casino pc USING(player_id) LEFT JOIN previous_sports ps USING(player_id)
  LEFT JOIN lifetime l USING(player_id)
  WHERE (:country='All markets' OR v.country=:country)
)
SELECT
  SUM(activity>0) active_players,
  SUM(previous_activity>0) previous_active_players,
  SUM(lifetime_ggr) lifetime_ggr,
  SUM(CASE WHEN activity>0 THEN remaining_ltv_90d ELSE 0 END) remaining_ltv_90d,
  SUM(CASE WHEN activity>0 AND churn_probability>=.70 THEN 1 ELSE 0 END) high_churn_risk,
  -- Filtered to players with a casino session in the period, matching queries/risk/metrics.py's
  -- "Predicted RG Interventions" population exactly, so both pages agree.
  SUM(CASE WHEN casino_sessions>0 AND rg_risk>=.55 THEN 1 ELSE 0 END) rg_interventions
FROM base
"""


def run(ctx):
    extra = {"prev_start": ctx.previous_params["start"], "prev_end": ctx.previous_params["end"]}
    return ctx.query(SQL, extra).iloc[0]
