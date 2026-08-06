from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ml.shared.config import MODEL_VERSION, RANDOM_STATE

METRICS = ["ggr", "rtp", "deposits", "player_activity", "channel_performance", "event_exposure"]


def run(daily: pd.DataFrame, measured_at: str) -> pd.DataFrame:
    """Flag unusual observations in each operational daily metric via Isolation Forest."""
    frame = daily.copy()
    records = []
    for metric in METRICS:
        values = frame[[metric]].to_numpy()
        detector = IsolationForest(n_estimators=90, contamination=.045, random_state=RANDOM_STATE).fit(values)
        score = -detector.score_samples(values)
        threshold = np.quantile(score, .955)
        baseline = frame[metric].rolling(28, min_periods=7).median()
        for index in np.flatnonzero(score >= threshold)[-8:]:
            current = float(frame.loc[index, metric])
            usual = float(baseline.iloc[index] if pd.notna(baseline.iloc[index]) else frame[metric].median())
            records.append((
                str(frame.loc[index, "date"]), metric, current, usual, float(score[index]),
                "High" if score[index] >= np.quantile(score, .98) else "Medium",
                "Isolation Forest + rolling median", MODEL_VERSION, measured_at,
            ))
    return pd.DataFrame(records, columns=["detected_date", "metric", "current_value", "usual_value", "anomaly_score", "severity", "method", "model_version", "detected_at"])
