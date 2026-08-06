from __future__ import annotations

"""Predicted Targetable Players, Estimated Campaign Opportunity and Predicted Risk Suppressions."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT COALESCE(SUM(fraud_risk<.55 AND rg_risk<.55),0) targetable,COALESCE(SUM(NOT(fraud_risk<.55 AND rg_risk<.55)),0) suppressed,COALESCE(SUM(CASE WHEN fraud_risk<.55 AND rg_risk<.55 AND recommended_action IN ('Send retention campaign','Offer governed bonus','Recommend preferred game') THEN predicted_ltv_90d*.08 ELSE 0 END),0) revenue FROM v_player_scores v WHERE {ACTIVE_CONDITION}"""


def run(ctx):
    return ctx.query(SQL).iloc[0]
