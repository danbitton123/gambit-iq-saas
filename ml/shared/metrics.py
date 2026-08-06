from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, roc_auc_score

from ml.shared.config import MODEL_VERSION


def lift_at_decile(y: pd.Series, probability: np.ndarray) -> float:
    count = max(1, int(np.ceil(len(y) * .10)))
    top_rate = float(y.iloc[np.argsort(-probability)[:count]].mean())
    base_rate = float(y.mean())
    return top_rate / base_rate if base_rate else 0.0


def classification_metrics(y: pd.Series, probability: np.ndarray) -> dict[str, float]:
    prediction = probability >= .5
    auc = roc_auc_score(y, probability) if y.nunique() > 1 else .5
    return {
        "roc_auc": float(auc), "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "lift_top_10pct": float(lift_at_decile(y.reset_index(drop=True), probability)),
        "positive_rate": float(y.mean()),
    }


def metric_rows(model: str, horizon: int | None, split: str, values: dict, measured_at: str) -> list[tuple]:
    return [(model, horizon, split, key, round(float(value), 5), MODEL_VERSION, measured_at) for key, value in values.items()]
