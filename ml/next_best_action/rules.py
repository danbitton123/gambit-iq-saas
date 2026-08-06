from __future__ import annotations

import numpy as np
import pandas as pd

from ml.shared.config import MODEL_VERSION

ACTIONS = ["Limit communications · RG review", "Manual fraud review", "Send retention campaign", "Recommend preferred game", "Offer governed bonus"]
REASONS = ["Responsible Gaming safeguard", "Payment anomaly", "High churn × future value", "Value retention opportunity", "High future value"]


def compute(current: pd.DataFrame, predictions: pd.DataFrame, measured_at: str) -> pd.DataFrame:
    """Rank each player into a governed action: RG/fraud safeguards outrank commercial actions."""
    merged = current[["player_id", "country", "channel", "vip_level", "historical_ggr"]].merge(predictions, on="player_id")
    rg_proxy = np.clip((current.max_duration.to_numpy() / 240) * .45 + (current.deposit_amount.to_numpy() > 1500) * .35, 0, 1)
    fraud_proxy = np.clip(current.decline_rate.to_numpy() * 1.4, 0, 1)
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
    merged["recommended_action"] = np.select(conditions, ACTIONS, default="Do nothing")
    merged["action_confidence"] = np.clip(.62 + np.abs(merged.churn_probability_30d - .5) * .45, .62, .94)
    merged["estimated_value_at_stake"] = merged.remaining_ltv_90d * merged.churn_probability_30d
    merged["reason"] = np.select(conditions, REASONS, default="No material intervention signal")
    merged["model_version"], merged["scored_at"] = MODEL_VERSION, measured_at
    return merged[["player_id", "recommended_action", "reason", "action_confidence", "estimated_value_at_stake", "model_version", "scored_at"]]
