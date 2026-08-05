from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


RANDOM_STATE = 2026
MODEL_VERSION = "2026.08-rf-v1"
CUTOFF = "2026-06-30 23:59:59"
END = "2026-08-05 00:00:00"

NUMERIC_FEATURES = [
    "tenure_days", "session_count", "active_days", "recency_days", "total_bets",
    "historical_ggr", "avg_duration", "max_duration", "distinct_games", "bet_count",
    "deposit_count", "deposit_amount", "withdrawal_count", "withdrawal_amount",
    "decline_rate", "payment_methods", "sports_bets", "sports_stake", "sports_ggr",
]
CATEGORICAL_FEATURES = ["country", "channel", "device", "vip_level", "kyc_status"]


FEATURE_SQL = """
WITH session_hist AS (
    SELECT player_id,
           COUNT(*) AS session_count,
           COUNT(DISTINCT DATE(session_start)) AS active_days,
           CAST(julianday(:cutoff) - julianday(MAX(session_start)) AS INTEGER) AS recency_days,
           SUM(total_bet_amount) AS total_bets,
           SUM(casino_ggr) AS historical_ggr,
           AVG(duration_minutes) AS avg_duration,
           MAX(duration_minutes) AS max_duration,
           COUNT(DISTINCT game_id) AS distinct_games,
           SUM(bet_count) AS bet_count
    FROM sessions WHERE session_start <= :cutoff GROUP BY player_id
), transaction_hist AS (
    SELECT player_id,
           SUM(CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN 1 ELSE 0 END) AS deposit_count,
           SUM(CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN amount ELSE 0 END) AS deposit_amount,
           SUM(CASE WHEN transaction_type='Withdrawal' AND transaction_status='Approved' THEN 1 ELSE 0 END) AS withdrawal_count,
           SUM(CASE WHEN transaction_type='Withdrawal' AND transaction_status='Approved' THEN amount ELSE 0 END) AS withdrawal_amount,
           AVG(CASE WHEN transaction_status='Declined' THEN 1.0 ELSE 0.0 END) AS decline_rate,
           COUNT(DISTINCT payment_method) AS payment_methods
    FROM transactions WHERE transaction_date <= :cutoff GROUP BY player_id
), sport_hist AS (
    SELECT player_id, COUNT(*) AS sports_bets, SUM(stake) AS sports_stake,
           SUM(sportsbook_ggr) AS sports_ggr
    FROM sports_bets WHERE bet_date <= :cutoff GROUP BY player_id
), future_activity AS (
    SELECT player_id, SUM(activity_count) AS future_activity,
           SUM(future_ggr) AS future_ggr, SUM(future_duration) AS future_duration
    FROM (
        SELECT player_id, COUNT(*) AS activity_count, SUM(casino_ggr) AS future_ggr,
               SUM(duration_minutes) AS future_duration
        FROM sessions WHERE session_start > :cutoff AND session_start < :end GROUP BY player_id
        UNION ALL
        SELECT player_id, COUNT(*) AS activity_count, SUM(sportsbook_ggr) AS future_ggr,
               0 AS future_duration
        FROM sports_bets WHERE bet_date > :cutoff AND bet_date < :end GROUP BY player_id
    ) GROUP BY player_id
), future_tx AS (
    SELECT player_id, COUNT(*) AS future_tx_count,
           SUM(CASE WHEN transaction_status='Declined' THEN 1 ELSE 0 END) AS future_declines,
           SUM(CASE WHEN transaction_type='Deposit' AND transaction_status='Approved' THEN amount ELSE 0 END) AS future_deposits,
           COUNT(DISTINCT DATE(transaction_date)) AS future_tx_days
    FROM transactions WHERE transaction_date > :cutoff AND transaction_date < :end GROUP BY player_id
)
SELECT p.player_id, p.country, p.channel, p.device, p.vip_level, p.kyc_status,
       CAST(julianday(:cutoff) - julianday(p.registration_date) AS INTEGER) AS tenure_days,
       COALESCE(s.session_count,0) AS session_count,
       COALESCE(s.active_days,0) AS active_days,
       COALESCE(s.recency_days,999) AS recency_days,
       COALESCE(s.total_bets,0) AS total_bets,
       COALESCE(s.historical_ggr,0) AS historical_ggr,
       COALESCE(s.avg_duration,0) AS avg_duration,
       COALESCE(s.max_duration,0) AS max_duration,
       COALESCE(s.distinct_games,0) AS distinct_games,
       COALESCE(s.bet_count,0) AS bet_count,
       COALESCE(t.deposit_count,0) AS deposit_count,
       COALESCE(t.deposit_amount,0) AS deposit_amount,
       COALESCE(t.withdrawal_count,0) AS withdrawal_count,
       COALESCE(t.withdrawal_amount,0) AS withdrawal_amount,
       COALESCE(t.decline_rate,0) AS decline_rate,
       COALESCE(t.payment_methods,0) AS payment_methods,
       COALESCE(sp.sports_bets,0) AS sports_bets,
       COALESCE(sp.sports_stake,0) AS sports_stake,
       COALESCE(sp.sports_ggr,0) AS sports_ggr,
       COALESCE(f.future_activity,0) AS future_activity,
       COALESCE(f.future_ggr,0) AS future_ggr,
       COALESCE(f.future_duration,0) AS future_duration,
       COALESCE(ft.future_tx_count,0) AS future_tx_count,
       COALESCE(ft.future_declines,0) AS future_declines,
       COALESCE(ft.future_deposits,0) AS future_deposits,
       COALESCE(ft.future_tx_days,0) AS future_tx_days,
       (SELECT MAX(session_start) FROM sessions sx WHERE sx.player_id=p.player_id) AS last_session
FROM players p
LEFT JOIN session_hist s ON s.player_id=p.player_id
LEFT JOIN transaction_hist t ON t.player_id=p.player_id
LEFT JOIN sport_hist sp ON sp.player_id=p.player_id
LEFT JOIN future_activity f ON f.player_id=p.player_id
LEFT JOIN future_tx ft ON ft.player_id=p.player_id
WHERE p.registration_date <= :cutoff
"""


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))])
    return ColumnTransformer([("numeric", numeric, NUMERIC_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)])


def _classifier() -> Pipeline:
    return Pipeline([
        ("preprocess", _preprocessor()),
        ("model", RandomForestClassifier(n_estimators=140, max_depth=11, min_samples_leaf=5, class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1)),
    ])


def _regressor() -> Pipeline:
    return Pipeline([
        ("preprocess", _preprocessor()),
        ("model", RandomForestRegressor(n_estimators=160, max_depth=12, min_samples_leaf=4, random_state=RANDOM_STATE, n_jobs=-1)),
    ])


def _safe_auc(y_true, probability) -> float:
    return float(roc_auc_score(y_true, probability)) if pd.Series(y_true).nunique() > 1 else 0.5


def train_and_score(db_path: Path, model_dir: Path | None = None) -> dict:
    model_dir = model_dir or db_path.parent.parent / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        dataset = pd.read_sql_query(FEATURE_SQL, conn, params={"cutoff": CUTOFF, "end": END})
        daily_revenue = pd.read_sql_query("""
            SELECT date, SUM(ggr) AS revenue FROM (
              SELECT DATE(session_start) date, SUM(casino_ggr) ggr FROM sessions GROUP BY DATE(session_start)
              UNION ALL SELECT DATE(bet_date), SUM(sportsbook_ggr) FROM sports_bets GROUP BY DATE(bet_date)
            ) GROUP BY date ORDER BY date
        """, conn)

    # Outcome labels are derived only from the period after the feature cutoff.
    dataset["churn_target"] = (dataset["future_activity"] == 0).astype(int)
    dataset["ltv_target"] = np.clip(dataset["future_ggr"], 0, None) * (90 / 35)
    dataset["fraud_target"] = (
        (dataset["future_tx_count"] >= 2)
        & (dataset["future_declines"] / dataset["future_tx_count"].clip(lower=1) >= .30)
    ).astype(int)
    duration_cutoff = max(dataset["future_duration"].quantile(.90), 60)
    deposit_cutoff = max(dataset["future_deposits"].quantile(.92), 100)
    dataset["rg_target"] = (
        (dataset["future_duration"] >= duration_cutoff)
        | ((dataset["future_deposits"] >= deposit_cutoff) & (dataset["future_activity"] >= 8))
    ).astype(int)

    X = dataset[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    train_idx, test_idx = train_test_split(np.arange(len(dataset)), test_size=.22, random_state=RANDOM_STATE, stratify=dataset["churn_target"])
    metrics: dict[str, dict] = {}
    predictions: dict[str, np.ndarray] = {}

    for name, target in [("churn", "churn_target"), ("fraud", "fraud_target"), ("responsible_gaming", "rg_target")]:
        if dataset[target].nunique() < 2:
            raise ValueError(f"Training target {target} contains only one class; adjust the label window before deployment.")
        model = _classifier()
        model.fit(X.iloc[train_idx], dataset[target].iloc[train_idx])
        test_probability = model.predict_proba(X.iloc[test_idx])[:, 1]
        test_prediction = (test_probability >= .5).astype(int)
        metrics[name] = {
            "roc_auc": round(_safe_auc(dataset[target].iloc[test_idx], test_probability), 4),
            "f1": round(float(f1_score(dataset[target].iloc[test_idx], test_prediction, zero_division=0)), 4),
            "positive_rate": round(float(dataset[target].mean()), 4),
        }
        model.fit(X, dataset[target])
        predictions[name] = model.predict_proba(X)[:, 1]
        joblib.dump(model, model_dir / f"{name}_model.joblib")

    ltv_model = _regressor()
    ltv_model.fit(X.iloc[train_idx], dataset["ltv_target"].iloc[train_idx])
    ltv_test = np.clip(ltv_model.predict(X.iloc[test_idx]), 0, None)
    metrics["ltv"] = {
        "mae": round(float(mean_absolute_error(dataset["ltv_target"].iloc[test_idx], ltv_test)), 2),
        "r2": round(float(r2_score(dataset["ltv_target"].iloc[test_idx], ltv_test)), 4),
        "mean_target": round(float(dataset["ltv_target"].mean()), 2),
    }
    ltv_model.fit(X, dataset["ltv_target"])
    predictions["ltv"] = np.clip(ltv_model.predict(X), 0, None)
    joblib.dump(ltv_model, model_dir / "ltv_model.joblib")

    # A fifth model forecasts daily NGR using lagged SQL revenue and calendar features.
    daily_revenue["date"] = pd.to_datetime(daily_revenue["date"])
    daily_revenue["dow"] = daily_revenue.date.dt.dayofweek
    daily_revenue["lag_1"] = daily_revenue.revenue.shift(1)
    daily_revenue["lag_7"] = daily_revenue.revenue.shift(7)
    daily_revenue["rolling_7"] = daily_revenue.revenue.shift(1).rolling(7).mean()
    revenue_train = daily_revenue.dropna().copy()
    revenue_features = ["dow", "lag_1", "lag_7", "rolling_7"]
    split = max(int(len(revenue_train) * .80), 1)
    revenue_model = RandomForestRegressor(n_estimators=240, max_depth=9, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=-1)
    revenue_model.fit(revenue_train[revenue_features].iloc[:split], revenue_train.revenue.iloc[:split])
    revenue_test = revenue_model.predict(revenue_train[revenue_features].iloc[split:])
    metrics["revenue_forecast"] = {
        "mae": round(float(mean_absolute_error(revenue_train.revenue.iloc[split:], revenue_test)), 2),
        "r2": round(float(r2_score(revenue_train.revenue.iloc[split:], revenue_test)), 4),
    }
    revenue_model.fit(revenue_train[revenue_features], revenue_train.revenue)
    joblib.dump(revenue_model, model_dir / "revenue_forecast_model.joblib")
    values = daily_revenue.set_index("date").revenue.copy()
    forecast_rows = []
    for forecast_date in pd.date_range(values.index.max() + pd.Timedelta(1, unit="D"), periods=30):
        features = pd.DataFrame([{"dow": forecast_date.dayofweek, "lag_1": values.iloc[-1], "lag_7": values.iloc[-7], "rolling_7": values.iloc[-7:].mean()}])
        forecast_value = max(float(revenue_model.predict(features)[0]), 0)
        values.loc[forecast_date] = forecast_value
        forecast_rows.append((forecast_date.strftime("%Y-%m-%d"), forecast_value, forecast_value * .78, forecast_value * 1.22, MODEL_VERSION))

    confidence = np.clip(.68 + np.abs(predictions["churn"] - .5) * .45, .68, .97)
    action = np.select(
        [predictions["responsible_gaming"] >= .55, predictions["fraud"] >= .55, (predictions["churn"] >= .70) & (predictions["ltv"] >= 500), predictions["ltv"] >= 1800],
        ["Player protection review", "Fraud review", "Retention review", "VIP review"],
        default="Monitor",
    )
    scores = pd.DataFrame({
        "player_id": dataset["player_id"],
        "predicted_ltv_90d": predictions["ltv"].round(2),
        "churn_probability": predictions["churn"].round(5),
        "fraud_risk": predictions["fraud"].round(5),
        "rg_risk": predictions["responsible_gaming"].round(5),
        "recommended_action": action,
        "model_confidence": confidence.round(5),
        "last_session": dataset["last_session"],
        "session_count": dataset["session_count"].astype(int),
        "lifetime_ggr": dataset["historical_ggr"].round(2),
        "model_version": MODEL_VERSION,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    })
    metric_rows = []
    for model_name, values in metrics.items():
        for metric_name, metric_value in values.items():
            metric_rows.append((model_name, metric_name, metric_value, MODEL_VERSION, datetime.now(timezone.utc).isoformat()))

    with sqlite3.connect(db_path) as conn:
        scores.to_sql("model_scores", conn, if_exists="replace", index=False)
        pd.DataFrame(metric_rows, columns=["model_name", "metric_name", "metric_value", "model_version", "measured_at"]).to_sql("model_metrics", conn, if_exists="replace", index=False)
        pd.DataFrame(forecast_rows, columns=["forecast_date", "predicted_revenue", "lower_bound", "upper_bound", "model_version"]).to_sql("revenue_forecast", conn, if_exists="replace", index=False)
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_model_scores_player ON model_scores(player_id);
            DROP VIEW IF EXISTS v_player_scores;
            CREATE VIEW v_player_scores AS
            SELECT p.*, m.predicted_ltv_90d, m.churn_probability, m.fraud_risk,
                   m.rg_risk, m.recommended_action, m.model_confidence,
                   m.last_session, m.session_count, m.lifetime_ggr,
                   m.model_version, m.scored_at
            FROM players p JOIN model_scores m ON m.player_id = p.player_id;
        """)

    report = {"model_version": MODEL_VERSION, "training_cutoff": CUTOFF, "rows": len(dataset), "metrics": metrics}
    (model_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    from config import DB_PATH

    print(json.dumps(train_and_score(DB_PATH), indent=2))
