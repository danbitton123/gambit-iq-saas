from __future__ import annotations

"""Observed FTD: players whose first-ever approved deposit falls inside the selected period."""

SQL = """
WITH first_deposit AS (
  SELECT player_id, MIN(transaction_date) ftd_date
  FROM transactions
  WHERE transaction_type='Deposit' AND transaction_status='Approved'
  GROUP BY player_id
)
SELECT COUNT(*) ftd_count
FROM first_deposit f JOIN players p USING(player_id)
WHERE f.ftd_date>=:start AND f.ftd_date<:end
  AND (:country='All markets' OR p.country=:country)
"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
