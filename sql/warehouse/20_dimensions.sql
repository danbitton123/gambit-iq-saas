-- DIMENSIONS: conformed descriptive entities.
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY, calendar_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL, quarter INTEGER NOT NULL, month INTEGER NOT NULL,
    month_name TEXT NOT NULL, week_of_year INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL, day_of_week INTEGER NOT NULL,
    day_name TEXT NOT NULL, is_weekend INTEGER NOT NULL
);
WITH RECURSIVE bounds AS (
  SELECT MIN(d) min_date, MAX(d) max_date FROM (
    SELECT MIN(registration_date) d FROM stg_players UNION ALL
    SELECT MIN(session_date) FROM stg_sessions UNION ALL
    SELECT MIN(transaction_day) FROM stg_transactions UNION ALL
    SELECT MIN(bet_day) FROM stg_sports_bets UNION ALL
    SELECT MAX(registration_date) FROM stg_players UNION ALL
    SELECT MAX(session_date) FROM stg_sessions UNION ALL
    SELECT MAX(transaction_day) FROM stg_transactions UNION ALL
    SELECT MAX(bet_day) FROM stg_sports_bets
  )
), dates(d) AS (
  SELECT min_date FROM bounds UNION ALL SELECT DATE(d,'+1 day') FROM dates,bounds WHERE d<max_date
)
INSERT INTO dim_date
SELECT CAST(strftime('%Y%m%d',d) AS INTEGER),d,CAST(strftime('%Y',d) AS INTEGER),
       ((CAST(strftime('%m',d) AS INTEGER)-1)/3)+1,CAST(strftime('%m',d) AS INTEGER),
       CASE strftime('%m',d) WHEN '01' THEN 'January' WHEN '02' THEN 'February' WHEN '03' THEN 'March' WHEN '04' THEN 'April' WHEN '05' THEN 'May' WHEN '06' THEN 'June' WHEN '07' THEN 'July' WHEN '08' THEN 'August' WHEN '09' THEN 'September' WHEN '10' THEN 'October' WHEN '11' THEN 'November' ELSE 'December' END,
       CAST(strftime('%W',d) AS INTEGER)+1,CAST(strftime('%d',d) AS INTEGER),
       CASE CAST(strftime('%w',d) AS INTEGER) WHEN 0 THEN 7 ELSE CAST(strftime('%w',d) AS INTEGER) END,
       CASE strftime('%w',d) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' ELSE 'Saturday' END,
       CASE WHEN strftime('%w',d) IN ('0','6') THEN 1 ELSE 0 END
FROM dates;

DROP TABLE IF EXISTS dim_player;
CREATE TABLE dim_player (
  player_id TEXT PRIMARY KEY, registration_at TEXT NOT NULL, registration_date TEXT NOT NULL,
  country TEXT NOT NULL, channel TEXT NOT NULL, device TEXT NOT NULL,
  vip_level TEXT NOT NULL, kyc_status TEXT NOT NULL, age_group TEXT NOT NULL
);
INSERT INTO dim_player SELECT player_id,registration_at,registration_date,country,channel,device,vip_level,kyc_status,age_group FROM stg_players;

DROP TABLE IF EXISTS dim_game;
CREATE TABLE dim_game (
  game_id TEXT PRIMARY KEY, game_name TEXT NOT NULL, game_family TEXT NOT NULL,
  theoretical_rtp REAL NOT NULL CHECK(theoretical_rtp BETWEEN 0 AND 1), provider TEXT NOT NULL
);
INSERT INTO dim_game SELECT game_id,game_name,game_family,theoretical_rtp,provider FROM stg_games;
