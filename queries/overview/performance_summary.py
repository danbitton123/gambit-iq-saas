from __future__ import annotations

"""Observed Total GGR, Estimated NGR, Active Players, Deposits and FTD — the "Performance at a glance" row."""

SQL = """
  WITH gaming AS (
    SELECT COALESCE(SUM(total_ggr),0) ggr,COALESCE(SUM(estimated_ngr),0) ngr,
           COALESCE(SUM(total_wagers),0) wagers,
           COALESCE(SUM(casino_payouts+sports_payout),0) payouts
    FROM mart_executive_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
      AND (:country='All markets' OR country=:country)
  ), active AS (
    SELECT COUNT(DISTINCT a.player_id) players FROM int_player_activity_daily a
    JOIN dim_player p USING(player_id) WHERE activity_date>=DATE(:start) AND activity_date<DATE(:end)
      AND (:country='All markets' OR p.country=:country)
  ), payments AS (
    SELECT COALESCE(SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END),0) deposits
    FROM v_transactions_enriched WHERE transaction_date>=:start AND transaction_date<:end
      AND (:country='All markets' OR country=:country)
  ), first_deposit AS (
    SELECT player_id,MIN(transaction_date) ftd_date FROM transactions
    WHERE transaction_type='Deposit' AND transaction_status='Approved' GROUP BY player_id
  ), ftd AS (
    SELECT COUNT(*) value FROM first_deposit f JOIN players p USING(player_id)
    WHERE ftd_date>=:start AND ftd_date<:end AND (:country='All markets' OR p.country=:country)
  ) SELECT gaming.*,active.players,payments.deposits,ftd.value ftd FROM gaming,active,payments,ftd
"""


def run(ctx):
    return ctx.query(SQL).iloc[0]


def run_previous(ctx):
    return ctx.previous_query(SQL).iloc[0]
