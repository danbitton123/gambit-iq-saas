-- INTERMEDIATE: reusable business logic, no dashboard formatting.
DROP VIEW IF EXISTS int_player_first_deposit;
CREATE VIEW int_player_first_deposit AS
SELECT player_id, MIN(transaction_date) AS ftd_at, DATE(MIN(transaction_date)) AS ftd_date
FROM fact_transaction WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id;

DROP VIEW IF EXISTS int_player_first_activity;
CREATE VIEW int_player_first_activity AS
SELECT player_id, MIN(activity_date) AS first_activity_date FROM (
  SELECT player_id,DATE(session_start) activity_date FROM fact_casino_session
  UNION ALL SELECT player_id,DATE(bet_date) FROM fact_sports_bet
) GROUP BY player_id;

DROP VIEW IF EXISTS int_player_activity_daily;
CREATE VIEW int_player_activity_daily AS
SELECT activity_date,player_id,MAX(casino_active) casino_active,MAX(sports_active) sports_active FROM (
  SELECT DATE(session_start) activity_date,player_id,1 casino_active,0 sports_active FROM fact_casino_session
  UNION ALL SELECT DATE(bet_date),player_id,0,1 FROM fact_sports_bet
) GROUP BY activity_date,player_id;

DROP VIEW IF EXISTS int_daily_gaming_revenue;
CREATE VIEW int_daily_gaming_revenue AS
SELECT calendar_date,country,SUM(casino_bets) casino_bets,SUM(casino_payouts) casino_payouts,
       SUM(casino_ggr) casino_ggr,SUM(sports_stake) sports_stake,SUM(sports_payout) sports_payout,
       SUM(sports_ggr) sports_ggr FROM (
  SELECT d.calendar_date,p.country,SUM(f.total_bet_amount) casino_bets,SUM(f.total_payout_amount) casino_payouts,SUM(f.casino_ggr) casino_ggr,0 sports_stake,0 sports_payout,0 sports_ggr
  FROM fact_casino_session f JOIN dim_date d USING(date_key) JOIN dim_player p USING(player_id) GROUP BY d.calendar_date,p.country
  UNION ALL
  SELECT d.calendar_date,p.country,0,0,0,SUM(f.stake),SUM(f.payout),SUM(f.sportsbook_ggr)
  FROM fact_sports_bet f JOIN dim_date d USING(date_key) JOIN dim_player p USING(player_id) GROUP BY d.calendar_date,p.country
) GROUP BY calendar_date,country;

-- Compatibility views allow incremental page migration without duplicate logic.
DROP VIEW IF EXISTS players;
CREATE VIEW players AS SELECT player_id,registration_at registration_date,country,channel,device,vip_level,kyc_status,age_group FROM dim_player;
DROP VIEW IF EXISTS games;
CREATE VIEW games AS SELECT * FROM dim_game;
DROP VIEW IF EXISTS sessions;
CREATE VIEW sessions AS SELECT session_id,player_id,game_id,session_start,duration_minutes,total_bet_amount,total_payout_amount,casino_ggr,bet_count FROM fact_casino_session;
DROP VIEW IF EXISTS transactions;
CREATE VIEW transactions AS SELECT transaction_id,player_id,transaction_date,transaction_type,amount,transaction_status,payment_method,processing_fee FROM fact_transaction;
DROP VIEW IF EXISTS sports_bets;
CREATE VIEW sports_bets AS SELECT bet_id,player_id,bet_date,sport,is_live,odds,stake,payout,sportsbook_ggr,event_name FROM fact_sports_bet;

DROP VIEW IF EXISTS v_sessions_enriched;
CREATE VIEW v_sessions_enriched AS SELECT f.session_id,f.player_id,f.game_id,f.session_start,f.duration_minutes,f.total_bet_amount,f.total_payout_amount,f.casino_ggr,f.bet_count,g.game_name,g.game_family,g.theoretical_rtp,g.provider,p.country,p.channel,p.device,p.vip_level,p.kyc_status FROM fact_casino_session f JOIN dim_game g USING(game_id) JOIN dim_player p USING(player_id);
DROP VIEW IF EXISTS v_transactions_enriched;
CREATE VIEW v_transactions_enriched AS SELECT f.transaction_id,f.player_id,f.transaction_date,f.transaction_type,f.amount,f.transaction_status,f.payment_method,f.processing_fee,p.country,p.channel,p.device,p.vip_level,p.kyc_status FROM fact_transaction f JOIN dim_player p USING(player_id);
DROP VIEW IF EXISTS v_sports_bets_enriched;
CREATE VIEW v_sports_bets_enriched AS SELECT f.bet_id,f.player_id,f.bet_date,f.sport,f.is_live,f.odds,f.stake,f.payout,f.sportsbook_ggr,f.event_name,p.country,p.channel,p.device,p.vip_level FROM fact_sports_bet f JOIN dim_player p USING(player_id);
