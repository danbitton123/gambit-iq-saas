from __future__ import annotations

"""Dynamic SQL segment sizes: high-value churn risk, new players, emerging VIP, dormant and bonus-sensitive."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT 'High-value churn risk' Segment,COUNT(*) Players FROM v_player_scores v WHERE churn_probability>.65 AND predicted_ltv_90d>500 AND {ACTIVE_CONDITION} UNION ALL SELECT 'New players',COUNT(*) FROM v_player_scores v WHERE registration_date>=:start AND registration_date<:end AND {ACTIVE_CONDITION} UNION ALL SELECT 'Emerging VIP',COUNT(*) FROM v_player_scores v WHERE predicted_ltv_90d>1200 AND vip_level<>'Platinum' AND {ACTIVE_CONDITION} UNION ALL SELECT 'Dormant 30D',COUNT(*) FROM v_player_scores v WHERE last_session<DATE(:end,'-30 day') AND (:country='All markets' OR v.country=:country) UNION ALL SELECT 'Bonus sensitive',COUNT(*) FROM v_player_scores v WHERE fraud_risk BETWEEN .25 AND .55 AND {ACTIVE_CONDITION}"""


def run(ctx):
    return ctx.query(SQL)
