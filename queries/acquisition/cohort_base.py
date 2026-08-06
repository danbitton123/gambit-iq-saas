from __future__ import annotations

"""Shared mature-registration cohort (complete 30-day observation window) reused by every
Acquisition query: adds FTD date, D30 conversion flag and the demo acquisition-cost assumption
per player. Every query in this page builds on top of the `b` CTE this defines."""

BASE_SQL = """WITH ftd AS (
  SELECT player_id, MIN(transaction_date) ftd_date FROM transactions
  WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id
), b AS (
  SELECT p.*, v.predicted_ltv_90d, v.churn_probability, v.fraud_risk, ftd.ftd_date,
    CASE WHEN ftd.ftd_date>=p.registration_date AND ftd.ftd_date<DATETIME(p.registration_date,'+30 days') THEN 1 ELSE 0 END converted_d30,
    CASE p.channel WHEN 'Google' THEN 34 WHEN 'Meta' THEN 38 WHEN 'Organic' THEN 8 WHEN 'Affiliate Alpha' THEN 47 WHEN 'Affiliate Nova' THEN 61 WHEN 'Influencers' THEN 73 ELSE 40 END acquisition_cost
  FROM players p JOIN v_player_scores v USING(player_id) LEFT JOIN ftd USING(player_id)
  WHERE p.registration_date>=:start AND p.registration_date<:end
    AND p.registration_date<=DATETIME(:end,'-30 days')
    AND (:country='All markets' OR p.country=:country)
) """
