from __future__ import annotations

"""Observed deposit approval rate — feeds the "Payment risk" alert (change vs. previous period)."""

SQL = """SELECT AVG(transaction_status='Approved') approval FROM v_transactions_enriched
      WHERE transaction_date>=:start AND transaction_date<:end AND transaction_type='Deposit'
      AND (:country='All markets' OR country=:country)"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
