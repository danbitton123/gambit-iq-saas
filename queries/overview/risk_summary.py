from __future__ import annotations

"""Scored active players, average churn probability, high-churn count/value-at-risk, future LTV and payment risk."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT COUNT(*) scored,AVG(churn_probability) churn_rate,
  SUM(churn_probability>=.70) high_churn,SUM(CASE WHEN churn_probability>=.70 THEN predicted_ltv_90d ELSE 0 END) value_at_risk,
  SUM(predicted_ltv_90d) future_ltv,AVG(model_confidence) confidence,
  SUM(fraud_risk>=.55) payment_risk FROM v_player_scores v WHERE {ACTIVE_CONDITION}"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
