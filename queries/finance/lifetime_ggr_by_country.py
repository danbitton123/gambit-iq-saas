from __future__ import annotations

"""Lifetime GGR per country for scored players in the selected market — long-run context, not period profitability."""

SQL = """SELECT country,SUM(lifetime_ggr) lifetime_ggr FROM v_player_scores WHERE (:country='All markets' OR country=:country) GROUP BY country ORDER BY lifetime_ggr"""


def run(ctx):
    return ctx.query(SQL)
