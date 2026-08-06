from __future__ import annotations

import sqlite3
from datetime import datetime, time, timedelta

import pandas as pd

NUMERIC_FEATURES = [
    "tenure_days", "session_count", "active_days", "recency_days", "total_bets",
    "historical_ggr", "avg_duration", "max_duration", "distinct_games", "bet_count",
    "deposit_count", "deposit_amount", "withdrawal_count", "withdrawal_amount",
    "decline_rate", "payment_methods", "sports_bets", "sports_stake", "sports_ggr",
]
CATEGORICAL_FEATURES = ["country", "channel", "device", "vip_level", "kyc_status"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Each horizon owns its observation windows. The latest window is a genuine test
# set and is never used for model selection or fitting.
TEMPORAL_WINDOWS = {
    7: {"train": ["2026-04-30", "2026-05-15"], "validation": ["2026-05-31"], "test": ["2026-06-30"]},
    14: {"train": ["2026-04-15", "2026-04-30"], "validation": ["2026-05-31"], "test": ["2026-06-30"]},
    30: {"train": ["2026-03-31", "2026-04-30"], "validation": ["2026-05-31"], "test": ["2026-06-30"]},
    90: {"train": ["2026-02-15", "2026-02-28"], "validation": ["2026-03-31"], "test": ["2026-04-30"]},
    180: {"train": ["2026-01-15", "2026-01-20"], "validation": ["2026-01-25"], "test": ["2026-02-05"]},
}

SNAPSHOT_SQL = """
WITH session_hist AS (
 SELECT player_id,COUNT(*) session_count,COUNT(DISTINCT DATE(session_start)) active_days,
 CAST(julianday(:cutoff)-julianday(MAX(session_start)) AS INTEGER) recency_days,
 MAX(session_start) last_session,
 SUM(total_bet_amount) total_bets,SUM(casino_ggr) historical_ggr,
 AVG(duration_minutes) avg_duration,MAX(duration_minutes) max_duration,
 COUNT(DISTINCT game_id) distinct_games,SUM(bet_count) bet_count
 FROM sessions WHERE session_start<=:cutoff GROUP BY player_id
), transaction_hist AS (
 SELECT player_id,
 SUM(transaction_type='Deposit' AND transaction_status='Approved') deposit_count,
 SUM(CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN amount ELSE 0 END) deposit_amount,
 SUM(transaction_type='Withdrawal' AND transaction_status='Approved') withdrawal_count,
 SUM(CASE WHEN transaction_type='Withdrawal' AND transaction_status='Approved' THEN amount ELSE 0 END) withdrawal_amount,
 AVG(transaction_status='Declined') decline_rate,COUNT(DISTINCT payment_method) payment_methods
 FROM transactions WHERE transaction_date<=:cutoff GROUP BY player_id
), sport_hist AS (
 SELECT player_id,COUNT(*) sports_bets,SUM(stake) sports_stake,SUM(sportsbook_ggr) sports_ggr,
 CAST(julianday(:cutoff)-julianday(MAX(bet_date)) AS INTEGER) sport_recency,MAX(bet_date) last_bet
 FROM sports_bets WHERE bet_date<=:cutoff GROUP BY player_id
), future AS (
 SELECT player_id,SUM(activity) future_activity,SUM(ggr) future_ggr FROM (
  SELECT player_id,COUNT(*) activity,SUM(casino_ggr) ggr FROM sessions
   WHERE session_start>:cutoff AND session_start<=:outcome_end GROUP BY player_id
  UNION ALL
  SELECT player_id,COUNT(*),SUM(sportsbook_ggr) FROM sports_bets
   WHERE bet_date>:cutoff AND bet_date<=:outcome_end GROUP BY player_id
 ) GROUP BY player_id
)
SELECT p.player_id,p.country,p.channel,p.device,p.vip_level,p.kyc_status,
 CAST(julianday(:cutoff)-julianday(p.registration_date) AS INTEGER) tenure_days,
 COALESCE(s.session_count,0) session_count,COALESCE(s.active_days,0) active_days,
 MIN(COALESCE(s.recency_days,999),COALESCE(sp.sport_recency,999)) recency_days,
 COALESCE(s.total_bets,0) total_bets,COALESCE(s.historical_ggr,0)+COALESCE(sp.sports_ggr,0) historical_ggr,
 COALESCE(s.avg_duration,0) avg_duration,COALESCE(s.max_duration,0) max_duration,
 COALESCE(s.distinct_games,0) distinct_games,COALESCE(s.bet_count,0) bet_count,
 COALESCE(t.deposit_count,0) deposit_count,COALESCE(t.deposit_amount,0) deposit_amount,
 COALESCE(t.withdrawal_count,0) withdrawal_count,COALESCE(t.withdrawal_amount,0) withdrawal_amount,
 COALESCE(t.decline_rate,0) decline_rate,COALESCE(t.payment_methods,0) payment_methods,
 COALESCE(sp.sports_bets,0) sports_bets,COALESCE(sp.sports_stake,0) sports_stake,
 COALESCE(sp.sports_ggr,0) sports_ggr,COALESCE(f.future_activity,0) future_activity,
 COALESCE(f.future_ggr,0) future_ggr,
 CASE WHEN COALESCE(s.last_session,'')>=COALESCE(sp.last_bet,'') THEN s.last_session ELSE sp.last_bet END last_activity,
 :cutoff snapshot_date
FROM players p LEFT JOIN session_hist s USING(player_id) LEFT JOIN transaction_hist t USING(player_id)
LEFT JOIN sport_hist sp USING(player_id) LEFT JOIN future f USING(player_id)
WHERE p.registration_date<=DATETIME(:cutoff,'-14 days')
  AND (COALESCE(s.session_count,0)+COALESCE(sp.sports_bets,0)+COALESCE(t.deposit_count,0))>0
"""


def snapshot(conn: sqlite3.Connection, cutoff: str, horizon: int) -> pd.DataFrame:
    """One row per eligible player with every model feature, as of `cutoff`, plus the outcome observed over the next `horizon` days."""
    cutoff_ts = datetime.combine(pd.Timestamp(cutoff).date(), time(23, 59, 59))
    outcome_end = cutoff_ts + timedelta(days=int(horizon))
    return pd.read_sql_query(SNAPSHOT_SQL, conn, params={
        "cutoff": cutoff_ts.strftime("%Y-%m-%d %H:%M:%S"),
        "outcome_end": outcome_end.strftime("%Y-%m-%d %H:%M:%S"),
    })


def temporal_dataset(conn: sqlite3.Connection, horizon: int) -> pd.DataFrame:
    """Stacked train/validation/test snapshots for one outcome horizon, per TEMPORAL_WINDOWS."""
    frames = []
    for split, cutoffs in TEMPORAL_WINDOWS[horizon].items():
        for cutoff in cutoffs:
            frame = snapshot(conn, cutoff, horizon)
            frame["split"] = split
            frames.append(frame)
    return pd.concat(frames, ignore_index=True)
