from __future__ import annotations

"""Estimated CAC, Predicted ROAS Proxy 90D and Predicted High Fraud-Risk Rate for the mature cohort."""

from .cohort_base import BASE_SQL

SQL = BASE_SQL + "SELECT AVG(acquisition_cost) cac,AVG(predicted_ltv_90d/acquisition_cost) roas,AVG(fraud_risk>=.55) fraud FROM b"


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
