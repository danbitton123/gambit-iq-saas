from __future__ import annotations

"""Daily observed payment approval rate — turns the "Observed Payment Approval Rate" KPI card
into a trend, using the same v_transactions_enriched source and scope as that KPI."""

SQL = """SELECT DATE(transaction_date) date,AVG(transaction_status='Approved') approval_rate,COUNT(*) transactions
FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end
AND (:country='All markets' OR country=:country) GROUP BY DATE(transaction_date) ORDER BY date"""


def run(ctx):
    return ctx.query(SQL)
