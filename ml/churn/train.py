from __future__ import annotations

import sqlite3
from pathlib import Path

import joblib
import pandas as pd

from ml.shared.features import FEATURES, temporal_dataset
from ml.shared.metrics import classification_metrics, metric_rows
from ml.shared.model_factory import classifier

HORIZONS = (7, 14, 30)


def train(conn: sqlite3.Connection, current: pd.DataFrame, model_dir: Path, measured_at: str):
    """Train the 7/14/30-day churn classifiers and score `current`.

    Returns (predictions, metric_rows, models) where `predictions` has one
    `churn_probability_{h}d` column per horizon plus `player_id`.
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    all_metric_rows, models = [], {}
    predictions = pd.DataFrame({"player_id": current.player_id})

    for horizon in HORIZONS:
        data = temporal_dataset(conn, horizon)
        data["target"] = (data.future_activity == 0).astype(int)
        train_split = data[data.split == "train"]
        validation = data[data.split == "validation"]
        test = data[data.split == "test"]
        model = classifier().fit(train_split[FEATURES], train_split.target)
        all_metric_rows += metric_rows(
            f"churn_{horizon}d", horizon, "validation",
            classification_metrics(validation.target, model.predict_proba(validation[FEATURES])[:, 1]), measured_at,
        )
        all_metric_rows += metric_rows(
            f"churn_{horizon}d", horizon, "test",
            classification_metrics(test.target, model.predict_proba(test[FEATURES])[:, 1]), measured_at,
        )
        # Refit only after immutable test metrics have been captured.
        model.fit(pd.concat([train_split, validation])[FEATURES], pd.concat([train_split, validation]).target)
        predictions[f"churn_probability_{horizon}d"] = model.predict_proba(current[FEATURES])[:, 1]
        models[f"churn_{horizon}d"] = model

    for name, model in models.items():
        joblib.dump(model, model_dir / f"{name}_model.joblib")
    return predictions, all_metric_rows, models
