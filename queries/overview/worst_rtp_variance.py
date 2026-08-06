from __future__ import annotations

"""The single game with the largest absolute variance from its theoretical RTP — feeds the "Casino RTP anomaly" alert."""

SQL = """SELECT game_name,SUM(payouts)/NULLIF(SUM(bets),0) actual_rtp,
      AVG(theoretical_rtp) theoretical_rtp,SUM(payouts)/NULLIF(SUM(bets),0)-AVG(theoretical_rtp) variance,SUM(bets) bets
      FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end)
      AND (:country='All markets' OR country=:country) GROUP BY game_name HAVING SUM(bets)>0
      ORDER BY ABS(variance) DESC LIMIT 1"""


def run(ctx):
    return ctx.query(SQL)
