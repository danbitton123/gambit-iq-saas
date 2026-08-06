from __future__ import annotations

"""Per payment-method volume, transaction count, approval/decline rate and fee performance."""

SQL = """SELECT payment_method,SUM(amount) Volume,COUNT(*) Transactions,AVG(transaction_status='Approved') Approved,AVG(transaction_status='Declined') Declined,SUM(processing_fee) Fees,SUM(processing_fee)/NULLIF(SUM(amount),0) Avg_fee FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end AND (:country='All markets' OR country=:country) GROUP BY payment_method ORDER BY Volume DESC"""


def run(ctx):
    return ctx.query(SQL)
