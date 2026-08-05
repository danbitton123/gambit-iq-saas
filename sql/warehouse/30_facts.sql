-- FACTS: validated events with keys, constraints and audit columns.
DROP TABLE IF EXISTS fact_casino_session;
CREATE TABLE fact_casino_session (
  session_id TEXT PRIMARY KEY, player_id TEXT NOT NULL, game_id TEXT NOT NULL,
  date_key INTEGER NOT NULL, session_start TEXT NOT NULL, duration_minutes REAL NOT NULL,
  total_bet_amount REAL NOT NULL CHECK(total_bet_amount>=0), total_payout_amount REAL NOT NULL CHECK(total_payout_amount>=0),
  casino_ggr REAL NOT NULL, bet_count INTEGER NOT NULL CHECK(bet_count>=0),
  loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(player_id) REFERENCES dim_player(player_id), FOREIGN KEY(game_id) REFERENCES dim_game(game_id), FOREIGN KEY(date_key) REFERENCES dim_date(date_key)
);
INSERT INTO fact_casino_session(session_id,player_id,game_id,date_key,session_start,duration_minutes,total_bet_amount,total_payout_amount,casino_ggr,bet_count)
SELECT session_id,player_id,game_id,CAST(strftime('%Y%m%d',session_date) AS INTEGER),session_start,duration_minutes,total_bet_amount,total_payout_amount,casino_ggr,bet_count FROM stg_sessions;

DROP TABLE IF EXISTS fact_transaction;
CREATE TABLE fact_transaction (
  transaction_id TEXT PRIMARY KEY, player_id TEXT NOT NULL, date_key INTEGER NOT NULL,
  transaction_date TEXT NOT NULL, transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Deposit','Withdrawal')),
  amount REAL NOT NULL CHECK(amount>=0), transaction_status TEXT NOT NULL,
  payment_method TEXT NOT NULL, processing_fee REAL NOT NULL CHECK(processing_fee>=0),
  loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(player_id) REFERENCES dim_player(player_id), FOREIGN KEY(date_key) REFERENCES dim_date(date_key)
);
INSERT INTO fact_transaction(transaction_id,player_id,date_key,transaction_date,transaction_type,amount,transaction_status,payment_method,processing_fee)
SELECT transaction_id,player_id,CAST(strftime('%Y%m%d',transaction_day) AS INTEGER),transaction_date,transaction_type,amount,transaction_status,payment_method,processing_fee FROM stg_transactions;

DROP TABLE IF EXISTS fact_sports_bet;
CREATE TABLE fact_sports_bet (
  bet_id TEXT PRIMARY KEY, player_id TEXT NOT NULL, date_key INTEGER NOT NULL,
  bet_date TEXT NOT NULL, sport TEXT NOT NULL, is_live INTEGER NOT NULL CHECK(is_live IN (0,1)),
  odds REAL NOT NULL CHECK(odds>=1), stake REAL NOT NULL CHECK(stake>=0), payout REAL NOT NULL CHECK(payout>=0),
  sportsbook_ggr REAL NOT NULL, event_name TEXT NOT NULL, loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(player_id) REFERENCES dim_player(player_id), FOREIGN KEY(date_key) REFERENCES dim_date(date_key)
);
INSERT INTO fact_sports_bet(bet_id,player_id,date_key,bet_date,sport,is_live,odds,stake,payout,sportsbook_ggr,event_name)
SELECT bet_id,player_id,CAST(strftime('%Y%m%d',bet_day) AS INTEGER),bet_date,sport,is_live,odds,stake,payout,sportsbook_ggr,event_name FROM stg_sports_bets;

CREATE INDEX IF NOT EXISTS idx_fact_session_date ON fact_casino_session(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_session_player ON fact_casino_session(player_id);
CREATE INDEX IF NOT EXISTS idx_fact_session_game ON fact_casino_session(game_id);
CREATE INDEX IF NOT EXISTS idx_fact_transaction_date ON fact_transaction(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_transaction_player ON fact_transaction(player_id);
CREATE INDEX IF NOT EXISTS idx_fact_sports_date ON fact_sports_bet(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sports_player ON fact_sports_bet(player_id);
