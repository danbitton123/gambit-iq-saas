from __future__ import annotations

"""Count of active, non-Platinum players at or above a given predicted_total_ltv_180d threshold.

SQLite has no native percentile function, so the 90th-percentile threshold itself is computed
once in pandas from the already SQL-sourced player_base column; only the count runs here as SQL.
Population matches the KPI_REGISTRY definition: active, non-Platinum players."""

from .player_base import SQL as PLAYER_BASE_SQL

SQL = """
SELECT COUNT(*) vip_candidates FROM ({base}) base_players
WHERE (sessions+sports_bets)>0 AND vip_level<>'Platinum' AND predicted_total_ltv_180d>=:threshold
""".format(base=PLAYER_BASE_SQL)


def run(ctx, threshold):
    return ctx.query(SQL, {"threshold": threshold}).iloc[0].vip_candidates
