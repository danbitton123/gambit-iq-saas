from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from ml.shared.config import MODEL_VERSION, RANDOM_STATE
from ml.shared.metrics import metric_rows

TARGETS = ("ggr", "ngr", "deposits", "ftd", "casino_ggr", "sportsbook_ggr")
FEATURE_NAMES = ["dow", "month", "lag_1", "lag_7", "lag_14", "rolling_7", "rolling_28"]
FORECAST_ROW_COLUMNS = ["metric", "forecast_date", "actual_value", "predicted_value", "lower_bound", "upper_bound", "split", "model_version"]


def daily_series(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("""
      WITH dates AS (SELECT calendar_date AS date FROM dim_date), casino AS (
       SELECT DATE(session_start) date,SUM(casino_ggr) casino_ggr,
        SUM(total_payout_amount)/NULLIF(SUM(total_bet_amount),0) rtp,COUNT(DISTINCT player_id) player_activity
       FROM sessions GROUP BY 1
      ), sports AS (
       SELECT DATE(bet_date) date,SUM(sportsbook_ggr) sportsbook_ggr FROM sports_bets GROUP BY 1
      ), tx AS (
       SELECT DATE(transaction_date) date,
        SUM(CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN amount ELSE 0 END) deposits,
        COUNT(DISTINCT CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN player_id END) ftd
       FROM transactions GROUP BY 1
      ), channel AS (
       SELECT date,MAX(ABS(channel_ggr)) channel_performance FROM (
        SELECT DATE(s.session_start) date,p.channel,SUM(s.casino_ggr) channel_ggr FROM sessions s JOIN players p USING(player_id)
        GROUP BY DATE(s.session_start),p.channel
       ) GROUP BY date
      ), event_risk AS (
       SELECT date,MAX(event_stake) event_exposure FROM (
        SELECT DATE(bet_date) date,event_name,SUM(stake) event_stake FROM sports_bets GROUP BY DATE(bet_date),event_name
       ) GROUP BY date
      ) SELECT d.date,COALESCE(c.casino_ggr,0) casino_ggr,COALESCE(s.sportsbook_ggr,0) sportsbook_ggr,
       COALESCE(c.casino_ggr,0)+COALESCE(s.sportsbook_ggr,0) ggr,
       (COALESCE(c.casino_ggr,0)+COALESCE(s.sportsbook_ggr,0))*.84 ngr,
       COALESCE(t.deposits,0) deposits,COALESCE(t.ftd,0) ftd,COALESCE(c.rtp,0) rtp,
       COALESCE(c.player_activity,0) player_activity,COALESCE(ch.channel_performance,0) channel_performance,
       COALESCE(e.event_exposure,0) event_exposure
      FROM dates d LEFT JOIN casino c USING(date) LEFT JOIN sports s USING(date) LEFT JOIN tx t USING(date)
      LEFT JOIN channel ch USING(date) LEFT JOIN event_risk e USING(date)
      WHERE d.date BETWEEN '2026-01-01' AND '2026-08-04' ORDER BY d.date
    """, conn)


def forecast_features(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    result = pd.DataFrame({"date": pd.to_datetime(frame.date), "actual": frame[target].astype(float)})
    result["dow"] = result.date.dt.dayofweek
    result["month"] = result.date.dt.month
    for lag in (1, 7, 14):
        result[f"lag_{lag}"] = result.actual.shift(lag)
    result["rolling_7"] = result.actual.shift(1).rolling(7).mean()
    result["rolling_28"] = result.actual.shift(1).rolling(28).mean()
    return result.dropna().reset_index(drop=True)


def train(conn: sqlite3.Connection, model_dir: Path, measured_at: str):
    """Train one daily forecaster per target in TARGETS.

    Returns (forecast_rows, metric_rows, daily) where `forecast_rows` mixes
    validation/test backtests with 30 future days, and `daily` is the raw
    SQL-aggregated daily series (also consumed by anomaly detection).
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    daily = daily_series(conn)
    rows, all_metric_rows = [], []

    for target in TARGETS:
        data = forecast_features(daily, target)
        train_end, validation_end = int(len(data) * .65), int(len(data) * .82)
        train_split, validation, test = data.iloc[:train_end], data.iloc[train_end:validation_end], data.iloc[validation_end:]
        model = HistGradientBoostingRegressor(loss="squared_error", learning_rate=.09, max_iter=90, max_leaf_nodes=18, l2_regularization=1.2, random_state=RANDOM_STATE)
        model.fit(train_split[FEATURE_NAMES], train_split.actual)
        val_pred = np.clip(model.predict(validation[FEATURE_NAMES]), 0, None)
        test_pred = np.clip(model.predict(test[FEATURE_NAMES]), 0, None)
        residual = validation.actual.to_numpy() - val_pred
        low_q, high_q = np.quantile(residual, [.10, .90])
        for split_name, split, prediction in (("validation", validation, val_pred), ("test", test, test_pred)):
            all_metric_rows += metric_rows(f"forecast_{target}", None, split_name, {
                "mae": mean_absolute_error(split.actual, prediction),
                "wape": np.abs(split.actual.to_numpy() - prediction).sum() / max(split.actual.abs().sum(), 1),
                "interval_80_coverage": np.mean((split.actual.to_numpy() >= prediction + low_q) & (split.actual.to_numpy() <= prediction + high_q)),
            }, measured_at)
            rows += [
                (target, str(date.date()), float(actual), float(pred), max(float(pred + low_q), 0), max(float(pred + high_q), 0), split_name, MODEL_VERSION)
                for date, actual, pred in zip(split.date, split.actual, prediction)
            ]
        model.fit(pd.concat([train_split, validation])[FEATURE_NAMES], pd.concat([train_split, validation]).actual)
        joblib.dump(model, model_dir / f"forecast_{target}_model.joblib")
        history = daily.set_index(pd.to_datetime(daily.date))[target].astype(float).copy()
        forecast_start = history.index.max().date() + timedelta(days=1)
        for forecast_date in pd.date_range(forecast_start, periods=30):
            feature = pd.DataFrame([{
                "dow": forecast_date.dayofweek, "month": forecast_date.month,
                "lag_1": history.iloc[-1], "lag_7": history.iloc[-7], "lag_14": history.iloc[-14],
                "rolling_7": history.iloc[-7:].mean(), "rolling_28": history.iloc[-28:].mean(),
            }])
            prediction = max(float(model.predict(feature)[0]), 0)
            history.loc[forecast_date] = prediction
            rows.append((target, str(forecast_date.date()), None, prediction, max(prediction + low_q, 0), max(prediction + high_q, 0), "future", MODEL_VERSION))

    return rows, all_metric_rows, daily
