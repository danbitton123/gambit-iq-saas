from __future__ import annotations

"""Isolation Forest anomalies detected in the selected period, ranked by anomaly score."""

SQL = """SELECT detected_date,metric,current_value,usual_value,anomaly_score,severity,method
        FROM ml_anomalies WHERE detected_date>=DATE(:start) AND detected_date<DATE(:end)
        ORDER BY anomaly_score DESC"""


def run(ctx):
    return ctx.query(SQL)
