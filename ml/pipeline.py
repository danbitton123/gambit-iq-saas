from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml.anomaly_detection import detect as anomaly_detection
from ml.churn import train as churn_train
from ml.ltv import train as ltv_train
from ml.next_best_action import rules as next_best_action
from ml.revenue_forecast import train as revenue_forecast
from ml.shared.config import MODEL_VERSION, SCORING_CUTOFF
from ml.shared.features import TEMPORAL_WINDOWS, snapshot

__all__ = ["MODEL_VERSION", "TEMPORAL_WINDOWS", "train_and_score"]


def train_and_score(db_path: Path, model_dir: Path | None = None) -> dict:
    """Train every governed model, score the current player base and persist results.

    Orchestrates the per-KPI projects under ml/ (churn, ltv, revenue_forecast,
    anomaly_detection, next_best_action): each owns its own features/training/
    metrics and can be worked on independently, while this function keeps the
    single public contract every caller (Streamlit startup, tests, the CLI
    entry point below) relies on.
    """
    model_dir = model_dir or db_path.parent.parent / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    measured_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(db_path) as conn:
        current = snapshot(conn, SCORING_CUTOFF, 1)

        churn_predictions, churn_metrics, _ = churn_train.train(conn, current, model_dir / "churn", measured_at)
        ltv_predictions, ltv_metrics, _ = ltv_train.train(conn, current, model_dir / "ltv", measured_at)
        predictions = churn_predictions.merge(ltv_predictions, on="player_id", validate="one_to_one")
        player_metrics = churn_metrics + ltv_metrics

        forecast_rows, forecast_metrics, daily = revenue_forecast.train(conn, model_dir / "forecast", measured_at)
        anomalies = anomaly_detection.run(daily, measured_at)
        nba = next_best_action.compute(current, predictions, measured_at)

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
