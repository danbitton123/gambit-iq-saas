from __future__ import annotations

"""Approved deposit/withdrawal value grouped by calendar week — feeds the deposits vs withdrawals chart."""

SQL = """SELECT DATE(transaction_date,'-'||((CAST(strftime('%w',transaction_date) AS INT)+6)%7)||' day') week,transaction_type,SUM(amount) amount FROM v_transactions_enriched WHERE transaction_status='Approved' AND transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country) GROUP BY week,transaction_type ORDER BY week"""


def run(ctx):
    return ctx.query(SQL)
