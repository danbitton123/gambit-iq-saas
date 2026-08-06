from __future__ import annotations

"""Predicted Active Accounts Scored, High-Risk Cases, Estimated Fraud Exposure, Fraud Reviews and RG Interventions."""

from .active_condition import ACTIVE_CONDITION

SQL = f"""SELECT COUNT(*) accounts,SUM(fraud_risk>=.55 OR rg_risk>=.55) cases,SUM(CASE WHEN fraud_risk>=.55 THEN MAX(lifetime_ggr,0) ELSE 0 END) exposure,SUM(rg_risk>=.55) rg,SUM(fraud_risk>=.55) fraud FROM v_player_scores v WHERE {ACTIVE_CONDITION}"""


def run(ctx):
    return ctx.query(SQL).iloc[0]
