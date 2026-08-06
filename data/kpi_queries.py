"""Executable governed KPI definitions shared by dashboards and tests."""

OBSERVED_FTD_SQL = """
WITH first_deposit AS (
  SELECT player_id, MIN(transaction_date) ftd_date
  FROM transactions
  WHERE transaction_type='Deposit' AND transaction_status='Approved'
  GROUP BY player_id
)
SELECT COUNT(*) ftd_count
FROM first_deposit f JOIN players p USING(player_id)
WHERE f.ftd_date>=:start AND f.ftd_date<:end
  AND (:country='All markets' OR p.country=:country)
"""


OBSERVED_FTD_CONVERSION_D30_SQL = """
WITH first_deposit AS (
  SELECT player_id, MIN(transaction_date) ftd_date
  FROM transactions
  WHERE transaction_type='Deposit' AND transaction_status='Approved'
  GROUP BY player_id
), eligible AS (
  SELECT p.player_id, p.registration_date, f.ftd_date
  FROM players p LEFT JOIN first_deposit f USING(player_id)
  WHERE p.registration_date>=:start AND p.registration_date<:end
    AND p.registration_date<=DATETIME(:end,'-30 days')
    AND (:country='All markets' OR p.country=:country)
)
SELECT COUNT(*) eligible_registrations,
       COALESCE(SUM(ftd_date>=registration_date AND ftd_date<DATETIME(registration_date,'+30 days')),0) converted_d30,
       1.0*SUM(ftd_date>=registration_date AND ftd_date<DATETIME(registration_date,'+30 days'))/NULLIF(COUNT(*),0) ftd_conversion_d30
FROM eligible
"""


OBSERVED_RETENTION_D30_SQL = """
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


PLAYER_BASE_SQL = """
WITH casino AS (
  SELECT player_id,COUNT(*) sessions,SUM(duration_minutes) minutes,SUM(total_bet_amount) casino_bets,
         SUM(casino_ggr) casino_ggr,MAX(session_start) last_casino
  FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end GROUP BY player_id
), sports AS (
  SELECT player_id,COUNT(*) sports_bets,SUM(stake) sports_handle,SUM(sportsbook_ggr) sports_ggr,MAX(bet_date) last_sports
  FROM v_sports_bets_enriched WHERE bet_date>=:start AND bet_date<:end GROUP BY player_id
), payments AS (
  SELECT player_id,SUM(transaction_status='Approved' AND transaction_type='Deposit') deposit_count,
         SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END) deposits,
         SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END) withdrawals,
         MAX(transaction_date) last_payment
  FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end GROUP BY player_id
), lifetime AS (
  SELECT player_id,SUM(ggr) lifetime_ggr,MAX(activity_at) last_activity FROM (
    SELECT player_id,SUM(casino_ggr) ggr,MAX(session_start) activity_at FROM sessions GROUP BY player_id
    UNION ALL SELECT player_id,SUM(sportsbook_ggr),MAX(bet_date) FROM sports_bets GROUP BY player_id
  ) GROUP BY player_id
), ftd AS (
  SELECT player_id,MIN(transaction_date) ftd_date FROM transactions
  WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id
), favorite AS (
  SELECT player_id,game_name FROM (
    SELECT player_id,game_name,COUNT(*) uses,ROW_NUMBER() OVER(PARTITION BY player_id ORDER BY COUNT(*) DESC,game_name) rank
    FROM v_sessions_enriched GROUP BY player_id,game_name
  ) WHERE rank=1
)
SELECT v.player_id,v.country,v.channel,v.device,v.vip_level,v.kyc_status,v.registration_date,
       v.predicted_ltv_90d,v.churn_probability,v.churn_probability_7d,v.churn_probability_14d,v.churn_probability_30d,
       v.observed_value,v.remaining_ltv_30d,v.remaining_ltv_90d,v.remaining_ltv_180d,
       v.predicted_total_ltv_30d,v.predicted_total_ltv_90d,v.predicted_total_ltv_180d,
       v.fraud_risk,v.rg_risk,v.model_confidence,v.recommended_action,
       COALESCE(l.lifetime_ggr,0) lifetime_ggr,l.last_activity,f.ftd_date,COALESCE(c.sessions,0) sessions,
       COALESCE(c.minutes,0) minutes,COALESCE(c.casino_bets,0) casino_bets,COALESCE(c.casino_ggr,0) casino_ggr,
       COALESCE(s.sports_bets,0) sports_bets,COALESCE(s.sports_handle,0) sports_handle,COALESCE(s.sports_ggr,0) sports_ggr,
       COALESCE(t.deposit_count,0) deposit_count,COALESCE(t.deposits,0) deposits,COALESCE(t.withdrawals,0) withdrawals,
       COALESCE(fav.game_name,'No casino activity') favorite_game
FROM v_player_scores v LEFT JOIN casino c USING(player_id) LEFT JOIN sports s USING(player_id)
LEFT JOIN payments t USING(player_id) LEFT JOIN lifetime l USING(player_id) LEFT JOIN ftd f USING(player_id)
LEFT JOIN favorite fav USING(player_id) WHERE (:country='All markets' OR v.country=:country)
"""


# Every KPI card on Player 360 is computed here in one SQL pass instead of pandas
# aggregation over PLAYER_BASE_SQL, to keep "every dashboard KPI is calculated in
# SQL" true for this page too. Filter semantics mirror the page's previous pandas
# logic exactly (same date windows, same player universe) so displayed numbers are
# unchanged; :prev_start/:prev_end are the immediately preceding, equally sized period.
PLAYER_INTELLIGENCE_KPI_SUMMARY_SQL = """
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
  -- Filtered to players with a casino session in the period, matching pages/risk.py's
  -- "Predicted RG Interventions" population exactly, so both pages agree.
  SUM(CASE WHEN casino_sessions>0 AND rg_risk>=.55 THEN 1 ELSE 0 END) rg_interventions
FROM base
"""


# SQLite has no native percentile function, so the 90th-percentile threshold of
# predicted_total_ltv_180d is computed once in pandas from the SQL-sourced column
# already loaded for segmentation; the KPI count itself runs as a bound SQL query.
# Population matches the KPI_REGISTRY definition: active, non-Platinum players.
PLAYER_VIP_CANDIDATES_COUNT_SQL = """
SELECT COUNT(*) vip_candidates FROM ({base}) base_players
WHERE (sessions+sports_bets)>0 AND vip_level<>'Platinum' AND predicted_total_ltv_180d>=:threshold
""".format(base=PLAYER_BASE_SQL)
