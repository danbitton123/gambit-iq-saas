from __future__ import annotations

"""Active players grouped into Stable/Watch/High-risk churn bands, with predicted LTV proxy at risk per band."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT CASE WHEN churn_probability<.40 THEN 'Stable' WHEN churn_probability<.70 THEN 'Watch' ELSE 'High risk' END segment,
          COUNT(*) players,SUM(predicted_ltv_90d) ltv_proxy,AVG(model_confidence) confidence FROM v_player_scores v
          WHERE {ACTIVE_CONDITION} GROUP BY segment"""


def run(ctx):
    return ctx.query(SQL)
