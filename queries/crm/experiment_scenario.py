from __future__ import annotations

"""Demo scenario comparing Control, Manual CRM and AI decisioning against the estimated campaign opportunity.
Not an observed experiment — uplift figures are explicit demo assumptions (see KPI_REGISTRY)."""

SQL = """SELECT 'Control' Variant,0 revenue,0 uplift UNION ALL SELECT 'Manual CRM',:revenue*.44,.108 UNION ALL SELECT 'AI decisioning',:revenue,.236"""


def run(ctx, revenue):
    return ctx.query(SQL, {"revenue": float(revenue)})
