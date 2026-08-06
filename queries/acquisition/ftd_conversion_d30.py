from __future__ import annotations

"""Observed FTD Conversion D30: share of mature registrations making their first approved deposit within 30 days."""

SQL = """
WITH first_deposit AS (
  SELECT player_id, MIN(transaction_date) ftd_date
  FROM transactions
  WHERE transaction_type='Deposit' AND transaction_status='Approved'
  GROUP BY player_id
), eligible AS (
  SELECT p.player_id, p.registration_date, f.ftd_date
  FROM players p LEFT JOIN first_deposit f USING(player_id)
  WHERE p.registration_date>=:start AND p.registration_date<:end
    AND p.registration_date<=DATETIME(:end,'-30 days')
    AND (:country='All markets' OR p.country=:country)
)
SELECT COUNT(*) eligible_registrations,
       COALESCE(SUM(ftd_date>=registration_date AND ftd_date<DATETIME(registration_date,'+30 days')),0) converted_d30,
       1.0*SUM(ftd_date>=registration_date AND ftd_date<DATETIME(registration_date,'+30 days'))/NULLIF(COUNT(*),0) ftd_conversion_d30
FROM eligible
"""


def run(ctx):
    return ctx.query(SQL).iloc[0]
