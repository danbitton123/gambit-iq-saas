from __future__ import annotations

"""One row per player in the selected market: value, behavior, payments, favorite game and every
model score. The base dataset behind Player 360's segmentation, export and individual player record."""

SQL = """
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


def run(ctx):
    return ctx.query(SQL)


def run_previous(ctx):
    return ctx.previous_query(SQL)
