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
