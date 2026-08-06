from __future__ import annotations

import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from ml.shared.features import FEATURES, temporal_dataset
from ml.shared.metrics import metric_rows
from ml.shared.model_factory import regressor

HORIZONS = (30, 90, 180)


def train(conn: sqlite3.Connection, current: pd.DataFrame, model_dir: Path, measured_at: str):
    """Train the 30/90/180-day remaining-LTV regressors and score `current`.

    Returns (predictions, metric_rows, models). `predictions` has one
    `remaining_ltv_{h}d` column per horizon, `observed_value` (lifetime GGR to
    date) and the derived `predicted_total_ltv_{h}d` columns, plus `player_id`.
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    all_metric_rows, models = [], {}
    predictions = pd.DataFrame({"player_id": current.player_id})

    for horizon in HORIZONS:
        data = temporal_dataset(conn, horizon)
        data["target"] = data.future_ggr.clip(lower=0)
        train_split, validation, test = (data[data.split == name] for name in ("train", "validation", "test"))
        model = regressor().fit(train_split[FEATURES], train_split.target)
        for split_name, split_data in (("validation", validation), ("test", test)):
            pred = np.clip(model.predict(split_data[FEATURES]), 0, None)
            all_metric_rows += metric_rows(f"ltv_{horizon}d", horizon, split_name, {
                "mae": mean_absolute_error(split_data.target, pred),
                "wape": np.abs(split_data.target - pred).sum() / max(split_data.target.abs().sum(), 1),
            }, measured_at)
        model.fit(pd.concat([train_split, validation])[FEATURES], pd.concat([train_split, validation]).target)
        predictions[f"remaining_ltv_{horizon}d"] = np.clip(model.predict(current[FEATURES]), 0, None)
        models[f"ltv_{horizon}d"] = model

    predictions["observed_value"] = current.historical_ggr.to_numpy()
    predictions["predicted_total_ltv_30d"] = predictions.observed_value + predictions.remaining_ltv_30d
    predictions["predicted_total_ltv_90d"] = predictions.observed_value + predictions.remaining_ltv_90d
    predictions["predicted_total_ltv_180d"] = predictions.observed_value + predictions.remaining_ltv_180d

    for name, model in models.items():
        joblib.dump(model, model_dir / f"{name}_model.joblib")
    return predictions, all_metric_rows, models
