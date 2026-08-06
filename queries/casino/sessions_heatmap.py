from __future__ import annotations

"""Observed casino session counts by day-of-week x hour-of-day — feeds the activity heatmap."""

SQL = """SELECT CASE CAST(strftime('%w',session_start) AS INTEGER) WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' ELSE 'Sun' END day,CAST(strftime('%H',session_start) AS INTEGER) hour,COUNT(*) sessions FROM v_sessions_enriched WHERE session_start>=:start AND session_start<:end AND (:country='All markets' OR country=:country) GROUP BY day,hour"""


def run(ctx):
    return ctx.query(SQL)
