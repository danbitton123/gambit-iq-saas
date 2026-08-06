from __future__ import annotations

"""Top 120 active accounts above the fraud/RG review floor, ranked by severity — feeds the case-management queue."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT player_id,CASE WHEN rg_risk>=fraud_risk THEN 'Player protection' ELSE 'Fraud / AML' END trigger,CASE WHEN MAX(fraud_risk,rg_risk)>=.75 THEN 'Critical' WHEN MAX(fraud_risk,rg_risk)>=.55 THEN 'High' ELSE 'Medium' END severity,model_confidence,recommended_action,CASE CAST(SUBSTR(player_id,-1) AS INTEGER)%3 WHEN 0 THEN 'Open' WHEN 1 THEN 'In review' ELSE 'Pending info' END status,fraud_risk,rg_risk,predicted_ltv_90d,MAX(fraud_risk,rg_risk) risk_score FROM v_player_scores v WHERE (fraud_risk>=.40 OR rg_risk>=.40) AND {ACTIVE_CONDITION} ORDER BY risk_score DESC LIMIT 120"""


def run(ctx):
    return ctx.query(SQL)
