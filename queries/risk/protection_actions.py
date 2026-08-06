from __future__ import annotations

"""Required player-protection action counts: manual review, cooling-off, marketing suppression, source-of-funds."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT 'Manual review' action,COUNT(*) Cases FROM v_player_scores v WHERE (fraud_risk>=.55 OR rg_risk>=.55) AND {ACTIVE_CONDITION} UNION ALL SELECT 'Cooling-off reminder',COUNT(*) FROM v_player_scores v WHERE rg_risk>=.55 AND {ACTIVE_CONDITION} UNION ALL SELECT 'Marketing suppression',COUNT(*) FROM v_player_scores v WHERE rg_risk>=.40 AND {ACTIVE_CONDITION} UNION ALL SELECT 'Source-of-funds request',COUNT(*) FROM v_player_scores v WHERE fraud_risk>=.55 AND {ACTIVE_CONDITION}"""


def run(ctx):
    return ctx.query(SQL)
