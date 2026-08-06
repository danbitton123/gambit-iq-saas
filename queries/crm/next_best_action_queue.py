from __future__ import annotations

"""Top 10 safety-filtered players with an active Next Best Action, ranked by predicted value and confidence."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT player_id,recommended_action,predicted_ltv_90d,model_confidence FROM v_player_scores v WHERE fraud_risk<.55 AND rg_risk<.55 AND recommended_action<>'Do nothing' AND {ACTIVE_CONDITION} ORDER BY predicted_ltv_90d DESC,model_confidence DESC LIMIT 10"""


def run(ctx):
    return ctx.query(SQL)
