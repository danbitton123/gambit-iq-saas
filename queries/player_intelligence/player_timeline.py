from __future__ import annotations

"""One player's lifetime deposits, withdrawals and casino/sportsbook GGR by activity date."""

SQL = """SELECT event_date,SUM(deposits) deposits,SUM(withdrawals) withdrawals,SUM(casino_ggr) casino_ggr,SUM(sports_ggr) sports_ggr,SUM(events) events FROM (
          SELECT DATE(session_start) event_date,0 deposits,0 withdrawals,SUM(casino_ggr) casino_ggr,0 sports_ggr,COUNT(*) events FROM sessions WHERE player_id=:player_id GROUP BY DATE(session_start)
          UNION ALL SELECT DATE(bet_date),0,0,0,SUM(sportsbook_ggr),COUNT(*) FROM sports_bets WHERE player_id=:player_id GROUP BY DATE(bet_date)
          UNION ALL SELECT DATE(transaction_date),SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Deposit' THEN amount ELSE 0 END),SUM(CASE WHEN transaction_status='Approved' AND transaction_type='Withdrawal' THEN amount ELSE 0 END),0,0,COUNT(*) FROM transactions WHERE player_id=:player_id GROUP BY DATE(transaction_date)
        ) GROUP BY event_date ORDER BY event_date"""


def run(ctx, player_id):
    return ctx.query(SQL, {"player_id": player_id})
