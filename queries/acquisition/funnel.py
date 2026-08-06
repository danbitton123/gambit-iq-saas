from __future__ import annotations

"""Acquisition conversion funnel: estimated visits down to observed FTD D30 and estimated second deposit."""

from .cohort_base import BASE_SQL

SQL = BASE_SQL + "SELECT COUNT(*)*13 Visits,COUNT(*) Registrations,SUM(kyc_status='Verified') KYC,SUM(converted_d30) FTD,CAST(SUM(converted_d30)*.61 AS INT) SecondDeposit FROM b"


def run(ctx):
    return ctx.query(SQL).iloc[0]
