from __future__ import annotations

"""Per-game GGR, sessions, bets, payouts, actual/theoretical RTP and RTP variance."""

SQL = """SELECT game_name,MAX(theoretical_rtp) theoretical_rtp,SUM(ggr) GGR,SUM(sessions) Sessions,SUM(bets) Bets,SUM(payouts) Payout,SUM(payouts)/NULLIF(SUM(bets),0) actual_rtp,SUM(payouts)/NULLIF(SUM(bets),0)-SUM(bets*theoretical_rtp)/NULLIF(SUM(bets),0) rtp_variance,SUM(ggr)/NULLIF(SUM(sessions),0) ggr_per_session,SUM(ggr)/NULLIF(SUM(bets),0) ggr_margin FROM mart_game_performance_daily WHERE metric_date>=DATE(:start) AND metric_date<DATE(:end) AND (:country='All markets' OR country=:country) GROUP BY game_name ORDER BY GGR DESC"""


def run(ctx):
    return ctx.query(SQL)
