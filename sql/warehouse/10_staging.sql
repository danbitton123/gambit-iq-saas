-- STAGING: typing, standardization and row-level business controls.
DROP VIEW IF EXISTS stg_players;
CREATE VIEW stg_players AS
SELECT TRIM(player_id) AS player_id,
       DATETIME(registration_date) AS registration_at,
       DATE(registration_date) AS registration_date,
       TRIM(country) AS country,
       TRIM(channel) AS channel,
       TRIM(device) AS device,
       TRIM(vip_level) AS vip_level,
       TRIM(kyc_status) AS kyc_status,
       TRIM(age_group) AS age_group
FROM raw_players
WHERE player_id IS NOT NULL;

DROP VIEW IF EXISTS stg_games;
CREATE VIEW stg_games AS
SELECT TRIM(game_id) AS game_id, TRIM(game_name) AS game_name,
       TRIM(game_family) AS game_family, CAST(theoretical_rtp AS REAL) AS theoretical_rtp,
       TRIM(provider) AS provider
FROM raw_games
WHERE game_id IS NOT NULL AND theoretical_rtp BETWEEN 0 AND 1;

DROP VIEW IF EXISTS stg_sessions;
CREATE VIEW stg_sessions AS
SELECT TRIM(session_id) AS session_id, TRIM(player_id) AS player_id,
       TRIM(game_id) AS game_id, DATETIME(session_start) AS session_start,
       DATE(session_start) AS session_date, CAST(duration_minutes AS REAL) AS duration_minutes,
       CAST(total_bet_amount AS REAL) AS total_bet_amount,
       CAST(total_payout_amount AS REAL) AS total_payout_amount,
       CAST(total_bet_amount AS REAL) - CAST(total_payout_amount AS REAL) AS casino_ggr,
       CAST(bet_count AS INTEGER) AS bet_count
FROM raw_sessions
WHERE session_id IS NOT NULL AND player_id IS NOT NULL AND game_id IS NOT NULL
  AND total_bet_amount >= 0 AND total_payout_amount >= 0 AND duration_minutes >= 0;

DROP VIEW IF EXISTS stg_transactions;
CREATE VIEW stg_transactions AS
SELECT TRIM(transaction_id) AS transaction_id, TRIM(player_id) AS player_id,
       DATETIME(transaction_date) AS transaction_date, DATE(transaction_date) AS transaction_day,
       CASE WHEN transaction_type IN ('Deposit','Withdrawal') THEN transaction_type END AS transaction_type,
       CAST(amount AS REAL) AS amount, TRIM(transaction_status) AS transaction_status,
       TRIM(payment_method) AS payment_method, CAST(processing_fee AS REAL) AS processing_fee
FROM raw_transactions
WHERE transaction_id IS NOT NULL AND player_id IS NOT NULL AND amount >= 0
  AND transaction_type IN ('Deposit','Withdrawal')
  AND transaction_status IN ('Approved','Declined','Pending');

DROP VIEW IF EXISTS stg_sports_bets;
CREATE VIEW stg_sports_bets AS
SELECT TRIM(bet_id) AS bet_id, TRIM(player_id) AS player_id,
       DATETIME(bet_date) AS bet_date, DATE(bet_date) AS bet_day,
       TRIM(sport) AS sport, CAST(is_live AS INTEGER) AS is_live,
       CAST(odds AS REAL) AS odds, CAST(stake AS REAL) AS stake,
       CAST(payout AS REAL) AS payout, CAST(stake AS REAL)-CAST(payout AS REAL) AS sportsbook_ggr,
       TRIM(event_name) AS event_name
FROM raw_sports_bets
WHERE bet_id IS NOT NULL AND player_id IS NOT NULL AND stake >= 0 AND payout >= 0 AND odds >= 1;
