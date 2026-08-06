from __future__ import annotations

"""Approved deposits, withdrawals, processing fees and payment approval rate for the filtered period."""

SQL = """SELECT COALESCE(SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END),0) deposits,COALESCE(SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END),0) withdrawals,COALESCE(SUM(CASE WHEN transaction_status='Approved' THEN processing_fee ELSE 0 END),0) fees,AVG(transaction_status='Approved') approval FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country)"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
