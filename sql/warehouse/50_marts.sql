-- DATA MARTS: dashboard-ready daily aggregates.
DROP TABLE IF EXISTS mart_executive_daily;
CREATE TABLE mart_executive_daily AS
WITH activity AS (SELECT activity_date,country,COUNT(*) active_players FROM int_player_activity_daily a JOIN dim_player p USING(player_id) GROUP BY activity_date,country),
payments AS (SELECT d.calendar_date,p.country,SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END) deposits,SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END) withdrawals,SUM(CASE WHEN transaction_status='Approved' THEN processing_fee ELSE 0 END) payment_fees,AVG(transaction_status='Approved') payment_approval_rate FROM fact_transaction f JOIN dim_date d USING(date_key) JOIN dim_player p USING(player_id) GROUP BY d.calendar_date,p.country)
SELECT r.calendar_date metric_date,r.country,r.casino_bets,r.casino_payouts,r.casino_ggr,r.sports_stake,r.sports_payout,r.sports_ggr,
       r.casino_bets+r.sports_stake total_wagers,r.casino_ggr+r.sports_ggr total_ggr,
       (r.casino_ggr+r.sports_ggr)/NULLIF(r.casino_bets+r.sports_stake,0) ggr_margin,
       COALESCE(a.active_players,0) active_players,COALESCE(t.deposits,0) deposits,COALESCE(t.withdrawals,0) withdrawals,
       COALESCE(t.payment_fees,0) payment_fees,t.payment_approval_rate,
       (r.casino_ggr+r.sports_ggr)-COALESCE(t.payment_fees,0)-MAX(r.casino_ggr+r.sports_ggr,0)*.065-MAX(r.casino_ggr+r.sports_ggr,0)*.095 estimated_ngr,
       CURRENT_TIMESTAMP updated_at,'1.0' definition_version
FROM int_daily_gaming_revenue r LEFT JOIN activity a ON a.activity_date=r.calendar_date AND a.country=r.country LEFT JOIN payments t ON t.calendar_date=r.calendar_date AND t.country=r.country;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mart_exec_date_country ON mart_executive_daily(metric_date,country);

DROP TABLE IF EXISTS mart_game_performance_daily;
CREATE TABLE mart_game_performance_daily AS
SELECT d.calendar_date metric_date,p.country,g.game_id,g.game_name,g.game_family,g.provider,g.theoretical_rtp,
       COUNT(*) sessions,COUNT(DISTINCT f.player_id) active_players,SUM(f.total_bet_amount) bets,SUM(f.total_payout_amount) payouts,SUM(f.casino_ggr) ggr,
       SUM(f.casino_ggr)/NULLIF(SUM(f.total_bet_amount),0) ggr_margin,SUM(f.total_payout_amount)/NULLIF(SUM(f.total_bet_amount),0) actual_rtp,
       SUM(f.total_payout_amount)/NULLIF(SUM(f.total_bet_amount),0)-g.theoretical_rtp rtp_variance,
       SUM(f.casino_ggr)/NULLIF(COUNT(*),0) ggr_per_session,CURRENT_TIMESTAMP updated_at,'1.0' definition_version
FROM fact_casino_session f JOIN dim_date d USING(date_key) JOIN dim_player p USING(player_id) JOIN dim_game g USING(game_id)
GROUP BY d.calendar_date,p.country,g.game_id;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mart_game_date_country_game ON mart_game_performance_daily(metric_date,country,game_id);

DROP TABLE IF EXISTS mart_acquisition_daily;
CREATE TABLE mart_acquisition_daily AS
WITH registrations AS (SELECT registration_date metric_date,country,channel,COUNT(*) registrations,SUM(kyc_status='Verified') kyc_verified FROM dim_player GROUP BY registration_date,country,channel),
ftd AS (SELECT f.ftd_date metric_date,p.country,p.channel,COUNT(*) ftd FROM int_player_first_deposit f JOIN dim_player p USING(player_id) GROUP BY f.ftd_date,p.country,p.channel),
keys AS (SELECT metric_date,country,channel FROM registrations UNION SELECT metric_date,country,channel FROM ftd)
SELECT k.metric_date,k.country,k.channel,COALESCE(r.registrations,0) registrations,COALESCE(r.kyc_verified,0) kyc_verified,COALESCE(f.ftd,0) ftd,CURRENT_TIMESTAMP updated_at,'1.0' definition_version
FROM keys k LEFT JOIN registrations r USING(metric_date,country,channel) LEFT JOIN ftd f USING(metric_date,country,channel);
CREATE UNIQUE INDEX IF NOT EXISTS idx_mart_acq_date_country_channel ON mart_acquisition_daily(metric_date,country,channel);

DROP TABLE IF EXISTS mart_payments_daily;
CREATE TABLE mart_payments_daily AS
SELECT d.calendar_date metric_date,p.country,f.payment_method,f.transaction_type,
       COUNT(*) transactions,SUM(f.amount) volume,AVG(f.transaction_status='Approved') approval_rate,
       SUM(CASE WHEN f.transaction_status='Approved' THEN f.processing_fee ELSE 0 END) approved_fees,
       CURRENT_TIMESTAMP updated_at,'1.0' definition_version
FROM fact_transaction f JOIN dim_date d USING(date_key) JOIN dim_player p USING(player_id)
GROUP BY d.calendar_date,p.country,f.payment_method,f.transaction_type;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mart_payment_key ON mart_payments_daily(metric_date,country,payment_method,transaction_type);
