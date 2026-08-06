from __future__ import annotations

"""Every recorded validation/test metric for every trained model — the ML Lab scorecard source."""

SQL = """SELECT model_name,horizon_days,split,metric_name,metric_value,model_version,measured_at
        FROM model_metrics_v2 ORDER BY model_name,split,metric_name"""


def run(ctx):
    return ctx.repo.query(SQL)
