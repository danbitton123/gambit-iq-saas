from __future__ import annotations

import json
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


RANDOM_STATE = 2026
MODEL_VERSION = "2026.08-temporal-v2"
SCORED_AT = "2026-08-04 23:59:59"

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


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([("numeric", numeric, NUMERIC_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)])


def _classifier() -> Pipeline:
    return Pipeline([("preprocess", _preprocessor()), ("model", HistGradientBoostingClassifier(
        learning_rate=.085, max_iter=70, max_leaf_nodes=24, min_samples_leaf=30,
        l2_regularization=1.2, class_weight="balanced", random_state=RANDOM_STATE,
    ))])


def _regressor() -> Pipeline:
    return Pipeline([("preprocess", _preprocessor()), ("model", HistGradientBoostingRegressor(
        loss="absolute_error", learning_rate=.085, max_iter=70, max_leaf_nodes=24,
        min_samples_leaf=25, l2_regularization=1.0, random_state=RANDOM_STATE,
    ))])


def _snapshot(conn: sqlite3.Connection, cutoff: str, horizon: int) -> pd.DataFrame:
    cutoff_ts = datetime.combine(pd.Timestamp(cutoff).date(), time(23, 59, 59))
    outcome_end = cutoff_ts + timedelta(days=int(horizon))
    return pd.read_sql_query(SNAPSHOT_SQL, conn, params={
        "cutoff": cutoff_ts.strftime("%Y-%m-%d %H:%M:%S"),
        "outcome_end": outcome_end.strftime("%Y-%m-%d %H:%M:%S"),
    })


def _temporal_dataset(conn: sqlite3.Connection, horizon: int) -> pd.DataFrame:
    frames = []
    for split, cutoffs in TEMPORAL_WINDOWS[horizon].items():
        for cutoff in cutoffs:
            frame = _snapshot(conn, cutoff, horizon)
            frame["split"] = split
            frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _lift_at_decile(y: pd.Series, probability: np.ndarray) -> float:
    count = max(1, int(np.ceil(len(y) * .10)))
    top_rate = float(y.iloc[np.argsort(-probability)[:count]].mean())
    base_rate = float(y.mean())
    return top_rate / base_rate if base_rate else 0.0


def _classification_metrics(y: pd.Series, probability: np.ndarray) -> dict[str, float]:
    prediction = probability >= .5
    auc = roc_auc_score(y, probability) if y.nunique() > 1 else .5
    return {
        "roc_auc": float(auc), "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "lift_top_10pct": float(_lift_at_decile(y.reset_index(drop=True), probability)),
        "positive_rate": float(y.mean()),
    }


def _metric_rows(model: str, horizon: int | None, split: str, values: dict, measured_at: str) -> list[tuple]:
    return [(model, horizon, split, key, round(float(value), 5), MODEL_VERSION, measured_at) for key, value in values.items()]


def _train_player_models(conn: sqlite3.Connection, model_dir: Path, measured_at: str):
    metric_rows, models = [], {}
    current = _snapshot(conn, "2026-08-04", 1)
    predictions = pd.DataFrame({"player_id": current.player_id})

    for horizon in (7, 14, 30):
        data = _temporal_dataset(conn, horizon)
        data["target"] = (data.future_activity == 0).astype(int)
        train = data[data.split == "train"]
        validation = data[data.split == "validation"]
        test = data[data.split == "test"]
        model = _classifier().fit(train[FEATURES], train.target)
        metric_rows += _metric_rows(f"churn_{horizon}d", horizon, "validation", _classification_metrics(validation.target, model.predict_proba(validation[FEATURES])[:, 1]), measured_at)
        metric_rows += _metric_rows(f"churn_{horizon}d", horizon, "test", _classification_metrics(test.target, model.predict_proba(test[FEATURES])[:, 1]), measured_at)
        # Refit only after immutable test metrics have been captured.
        model.fit(pd.concat([train, validation])[FEATURES], pd.concat([train, validation]).target)
        predictions[f"churn_probability_{horizon}d"] = model.predict_proba(current[FEATURES])[:, 1]
        models[f"churn_{horizon}d"] = model

    for horizon in (30, 90, 180):
        data = _temporal_dataset(conn, horizon)
        data["target"] = data.future_ggr.clip(lower=0)
        train, validation, test = (data[data.split == name] for name in ("train", "validation", "test"))
        model = _regressor().fit(train[FEATURES], train.target)
        for split_name, split_data in (("validation", validation), ("test", test)):
            pred = np.clip(model.predict(split_data[FEATURES]), 0, None)
            metric_rows += _metric_rows(f"ltv_{horizon}d", horizon, split_name, {
                "mae": mean_absolute_error(split_data.target, pred),
                "wape": np.abs(split_data.target - pred).sum() / max(split_data.target.abs().sum(), 1),
            }, measured_at)
        model.fit(pd.concat([train, validation])[FEATURES], pd.concat([train, validation]).target)
        predictions[f"remaining_ltv_{horizon}d"] = np.clip(model.predict(current[FEATURES]), 0, None)
        models[f"ltv_{horizon}d"] = model

    predictions["observed_value"] = current.historical_ggr.to_numpy()
    predictions["predicted_total_ltv_30d"] = predictions.observed_value + predictions.remaining_ltv_30d
    predictions["predicted_total_ltv_90d"] = predictions.observed_value + predictions.remaining_ltv_90d
    predictions["predicted_total_ltv_180d"] = predictions.observed_value + predictions.remaining_ltv_180d
    for name, model in models.items():
        joblib.dump(model, model_dir / f"{name}_model.joblib")
    return current, predictions, metric_rows


def _daily_series(conn: sqlite3.Connection) -> pd.DataFrame:
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


def _forecast_features(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    result = pd.DataFrame({"date": pd.to_datetime(frame.date), "actual": frame[target].astype(float)})
    result["dow"] = result.date.dt.dayofweek
    result["month"] = result.date.dt.month
    for lag in (1, 7, 14): result[f"lag_{lag}"] = result.actual.shift(lag)
    result["rolling_7"] = result.actual.shift(1).rolling(7).mean()
    result["rolling_28"] = result.actual.shift(1).rolling(28).mean()
    return result.dropna().reset_index(drop=True)


def _train_forecasts(conn: sqlite3.Connection, model_dir: Path, measured_at: str):
    daily = _daily_series(conn)
    rows, metric_rows = [], []
    feature_names = ["dow", "month", "lag_1", "lag_7", "lag_14", "rolling_7", "rolling_28"]
    for target in ("ggr", "ngr", "deposits", "ftd", "casino_ggr", "sportsbook_ggr"):
        data = _forecast_features(daily, target)
        train_end, validation_end = int(len(data)*.65), int(len(data)*.82)
        train, validation, test = data.iloc[:train_end], data.iloc[train_end:validation_end], data.iloc[validation_end:]
        model = HistGradientBoostingRegressor(loss="squared_error", learning_rate=.09, max_iter=90, max_leaf_nodes=18, l2_regularization=1.2, random_state=RANDOM_STATE)
        model.fit(train[feature_names], train.actual)
        val_pred = np.clip(model.predict(validation[feature_names]), 0, None)
        test_pred = np.clip(model.predict(test[feature_names]), 0, None)
        residual = validation.actual.to_numpy()-val_pred
        low_q, high_q = np.quantile(residual, [.10, .90])
        for split_name, split, prediction in (("validation", validation, val_pred), ("test", test, test_pred)):
            metric_rows += _metric_rows(f"forecast_{target}", None, split_name, {
                "mae": mean_absolute_error(split.actual, prediction),
                "wape": np.abs(split.actual.to_numpy()-prediction).sum()/max(split.actual.abs().sum(), 1),
                "interval_80_coverage": np.mean((split.actual.to_numpy() >= prediction+low_q) & (split.actual.to_numpy() <= prediction+high_q)),
            }, measured_at)
            rows += [(target, str(date.date()), float(actual), float(pred), max(float(pred+low_q), 0), max(float(pred+high_q), 0), split_name, MODEL_VERSION)
                     for date, actual, pred in zip(split.date, split.actual, prediction)]
        model.fit(pd.concat([train, validation])[feature_names], pd.concat([train, validation]).actual)
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
            rows.append((target, str(forecast_date.date()), None, prediction, max(prediction+low_q,0), max(prediction+high_q,0), "future", MODEL_VERSION))
    return rows, metric_rows, daily


def _anomalies(daily: pd.DataFrame, measured_at: str) -> pd.DataFrame:
    metrics = ["ggr", "rtp", "deposits", "player_activity", "channel_performance", "event_exposure"]
    frame = daily.copy()
    records = []
    for metric in metrics:
        values = frame[[metric]].to_numpy()
        detector = IsolationForest(n_estimators=90, contamination=.045, random_state=RANDOM_STATE).fit(values)
        score = -detector.score_samples(values)
        threshold = np.quantile(score, .955)
        baseline = frame[metric].rolling(28, min_periods=7).median()
        for index in np.flatnonzero(score >= threshold)[-8:]:
            current, usual = float(frame.loc[index, metric]), float(baseline.iloc[index] if pd.notna(baseline.iloc[index]) else frame[metric].median())
            records.append((str(frame.loc[index, "date"]), metric, current, usual, float(score[index]), "High" if score[index] >= np.quantile(score,.98) else "Medium", "Isolation Forest + rolling median", MODEL_VERSION, measured_at))
    return pd.DataFrame(records, columns=["detected_date","metric","current_value","usual_value","anomaly_score","severity","method","model_version","detected_at"])


def _next_best_actions(current: pd.DataFrame, predictions: pd.DataFrame, measured_at: str) -> pd.DataFrame:
    merged = current[["player_id", "country", "channel", "vip_level", "historical_ggr"]].merge(predictions, on="player_id")
    rg_proxy = np.clip((current.max_duration.to_numpy()/240)*.45 + (current.deposit_amount.to_numpy()>1500)*.35, 0, 1)
    fraud_proxy = np.clip(current.decline_rate.to_numpy()*1.4, 0, 1)
    churn_high = merged.churn_probability_30d.quantile(.80)
    churn_medium = merged.churn_probability_14d.quantile(.55)
    value_medium = merged.remaining_ltv_90d.quantile(.60)
    value_high = merged.remaining_ltv_90d.quantile(.75)
    future_high = merged.remaining_ltv_180d.quantile(.90)
    conditions = [
        rg_proxy >= .55,
        fraud_proxy >= .55,
        (merged.churn_probability_30d >= churn_high) & (merged.remaining_ltv_90d >= value_medium),
        (merged.remaining_ltv_180d >= future_high) & (merged.churn_probability_30d < churn_high),
        (merged.remaining_ltv_90d >= value_high) & (merged.churn_probability_14d >= churn_medium),
    ]
    actions = ["Limit communications · RG review", "Manual fraud review", "Send retention campaign", "Recommend preferred game", "Offer governed bonus"]
    merged["recommended_action"] = np.select(conditions, actions, default="Do nothing")
    merged["action_confidence"] = np.clip(.62 + np.abs(merged.churn_probability_30d-.5)*.45, .62, .94)
    merged["estimated_value_at_stake"] = merged.remaining_ltv_90d * merged.churn_probability_30d
    merged["reason"] = np.select(conditions, ["Responsible Gaming safeguard", "Payment anomaly", "High churn × future value", "Value retention opportunity", "High future value"], default="No material intervention signal")
    merged["model_version"], merged["scored_at"] = MODEL_VERSION, measured_at
    return merged[["player_id","recommended_action","reason","action_confidence","estimated_value_at_stake","model_version","scored_at"]]


def train_and_score(db_path: Path, model_dir: Path | None = None) -> dict:
    model_dir = model_dir or db_path.parent.parent / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    measured_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        current, predictions, player_metrics = _train_player_models(conn, model_dir, measured_at)
        forecast_rows, forecast_metrics, daily = _train_forecasts(conn, model_dir, measured_at)
        anomalies = _anomalies(daily, measured_at)
        nba = _next_best_actions(current, predictions, measured_at)

        scores = predictions.assign(
            predicted_ltv_90d=predictions.remaining_ltv_90d,
            churn_probability=predictions.churn_probability_30d,
            fraud_risk=np.clip(current.decline_rate.to_numpy()*1.4, 0, 1),
            rg_risk=np.clip((current.max_duration.to_numpy()/240)*.45+(current.deposit_amount.to_numpy()>1500)*.35, 0, 1),
            recommended_action=nba.recommended_action,
            model_confidence=nba.action_confidence,
            last_session=current.last_activity, session_count=current.session_count.astype(int),
            lifetime_ggr=current.historical_ggr, model_version=MODEL_VERSION, scored_at=measured_at,
        )
        metric_columns = ["model_name","horizon_days","split","metric_name","metric_value","model_version","measured_at"]
        metrics = pd.DataFrame(player_metrics+forecast_metrics, columns=metric_columns)
        scores.to_sql("model_scores", conn, if_exists="replace", index=False)
        metrics.to_sql("model_metrics_v2", conn, if_exists="replace", index=False)
        metrics[["model_name","metric_name","metric_value","model_version","measured_at"]].to_sql("model_metrics", conn, if_exists="replace", index=False)
        pd.DataFrame(forecast_rows, columns=["metric","forecast_date","actual_value","predicted_value","lower_bound","upper_bound","split","model_version"]).to_sql("forecast_backtest", conn, if_exists="replace", index=False)
        legacy = pd.DataFrame(forecast_rows, columns=["metric","forecast_date","actual_value","predicted_value","lower_bound","upper_bound","split","model_version"])
        legacy = legacy[(legacy.metric=="ggr") & (legacy.split=="future")].rename(columns={"predicted_value":"predicted_revenue"})
        legacy[["forecast_date","predicted_revenue","lower_bound","upper_bound","model_version"]].to_sql("revenue_forecast", conn, if_exists="replace", index=False)
        anomalies.to_sql("ml_anomalies", conn, if_exists="replace", index=False)
        nba.to_sql("next_best_actions", conn, if_exists="replace", index=False)
        conn.execute("INSERT OR REPLACE INTO app_metadata VALUES('model_status','available')")
        conn.execute("INSERT OR REPLACE INTO app_metadata VALUES('model_version',?)", (MODEL_VERSION,))
        conn.commit()

    report = {
        "model_version": MODEL_VERSION,
        "temporal_policy": "past → recent validation → latest untouched test",
        "rows_scored": len(predictions),
        "rows": len(predictions),
        "metrics": metrics.to_dict("records"),
        "anomalies": len(anomalies),
        "next_best_actions": nba.recommended_action.value_counts().to_dict(),
    }
    (model_dir / "metrics.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    from config import DB_PATH
    print(json.dumps(train_and_score(DB_PATH), indent=2, default=str))
