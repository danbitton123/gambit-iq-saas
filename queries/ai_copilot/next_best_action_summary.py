from __future__ import annotations

"""Scored players and estimated value at stake grouped by recommended Next Best Action."""

SQL = """SELECT recommended_action,COUNT(*) players,SUM(estimated_value_at_stake) value_at_stake,
        AVG(action_confidence) confidence FROM next_best_actions GROUP BY recommended_action ORDER BY value_at_stake DESC"""


def run(ctx):
    return ctx.repo.query(SQL)
