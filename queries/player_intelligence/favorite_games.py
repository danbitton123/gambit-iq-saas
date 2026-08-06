from __future__ import annotations

"""Top 5 lifetime casino games for one player, ranked by session count."""

SQL = """SELECT game_name,COUNT(*) sessions,SUM(total_bet_amount) bets,SUM(casino_ggr) ggr
          FROM v_sessions_enriched WHERE player_id=:player_id GROUP BY game_name ORDER BY sessions DESC LIMIT 5"""


def run(ctx, player_id):
    return ctx.query(SQL, {"player_id": player_id})
