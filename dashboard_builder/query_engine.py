from __future__ import annotations

"""Executes Widget configs as governed SQL, reusing data/semantic_query.py's DATASETS catalog —
the exact same allow-listed tables/dimensions/metrics the AI Copilot's "Open data analysis"
answers from. A dashboard KPI and the same metric elsewhere in CasinoAI are therefore always the
same SQL expression against the same governed marts/views, not two independently maintained
calculations that can silently drift apart.
"""

from dataclasses import dataclass

import pandas as pd

from data.errors import DataConnectionError, SQLQueryError
from data.semantic_query import DATASETS, QueryPlan, validate_plan
from dashboard_builder.models import Dashboard, LocalFilter, Widget


def effective_filters(dashboard: Dashboard | None, widget: Widget) -> list[LocalFilter]:
    """Dashboard-level global filters apply to every widget whose dataset has that dimension;
    a widget's own local filter on the same dimension takes precedence (mirrors the "Dashboard:
    Germany / Chart local: Provider = Evolution" layering from the product spec)."""
    local_dimensions = {f.dimension for f in widget.filters}
    merged = list(widget.filters)
    if dashboard is not None:
        for global_filter in dashboard.global_filters:
            if global_filter.dataset != widget.dataset or global_filter.dimension in local_dimensions:
                continue
            if len(global_filter.values) == 1:
                merged.append(LocalFilter(dimension=global_filter.dimension, value=global_filter.values[0]))
    return merged


class WidgetDataError(Exception):
    """Raised for a widget configuration/query problem; the widget renderer catches this and
    shows an inline message instead of ever letting a chart take down the whole page."""


@dataclass(frozen=True)
class WidgetResult:
    frame: pd.DataFrame
    dimension_label: str | None
    measure_labels: list[str]


def distinct_values(ctx, dataset: str, dimension: str, limit: int = 200) -> list[str]:
    """Real values for a filter dropdown (never free text) — avoids typo'd filters that would
    silently return an empty chart instead of an error."""
    ds = DATASETS.get(dataset)
    if not ds or dimension not in ds.dimensions:
        return []
    sql = f"SELECT DISTINCT {ds.dimensions[dimension]} AS value FROM {ds.table} WHERE {ds.dimensions[dimension]} IS NOT NULL ORDER BY 1 LIMIT {limit}"
    try:
        frame = ctx.repo.query(sql)
    except (SQLQueryError, DataConnectionError):
        return []
    return [str(v) for v in frame["value"].tolist()]


def dataset_choices() -> dict[str, str]:
    labels = {
        "executive": "Executive overview", "casino": "Casino", "sportsbook": "Sportsbook",
        "payments": "Payments", "acquisition": "Acquisition", "players": "Players",
        "player_activity": "Player Activity",
    }
    return {key: labels.get(key, key.title()) for key in DATASETS}


def dimension_choices(dataset: str) -> dict[str, str]:
    ds = DATASETS.get(dataset)
    return {name: name.replace("_", " ").title() for name in ds.dimensions} if ds else {}


def measure_choices(dataset: str) -> dict[str, str]:
    ds = DATASETS.get(dataset)
    return {name: metric.label for name, metric in ds.metrics.items()} if ds else {}


def _build_plan(widget: Widget) -> QueryPlan | None:
    if not widget.dataset or widget.dataset not in DATASETS or not widget.measures:
        return None
    dimensions = tuple(d for d in (widget.dimension, widget.dimension2) if d)
    order_metric = widget.measures[0]
    chart_type = "table" if widget.type in ("table", "scatter") else ("line" if widget.type == "line" else "bar")
    plan = QueryPlan(
        dataset=widget.dataset, dimensions=dimensions, metrics=tuple(widget.measures[:3]),
        order_metric=order_metric, order_direction=widget.sort_direction.upper(),
        limit=widget.top_n or 100, chart_type=chart_type,
    )
    return validate_plan(plan)


def _compile(plan: QueryPlan, local_filters: list[LocalFilter]) -> tuple[str, dict]:
    """Mirrors SemanticQueryEngine._compile but also accepts widget-local equality filters —
    a capability the shared Copilot compiler doesn't need. Reads the same DATASETS catalog so
    the two compilers can never disagree on what a dimension or metric means."""
    ds = DATASETS[plan.dataset]
    dimensions = [f'{ds.dimensions[name]} AS "{name.replace("_"," ").title()}"' for name in plan.dimensions]
    metrics = [f'{ds.metrics[name].expression} AS "{name}"' for name in plan.metrics]
    clauses = []
    params: dict = {}
    if ds.date_field:
        # DATE(...) normalizes both sides — :start/:end are full datetime strings, but some
        # date_fields (e.g. mart_executive_daily.metric_date) store date-only text, and a plain
        # string comparison against a datetime string drops the boundary day. See the identical
        # fix and explanation in data/semantic_query.py::SemanticQueryEngine._compile.
        clauses.append(f"{ds.date_field}>=DATE(:start) AND {ds.date_field}<DATE(:end)")
    if "country" in ds.dimensions:
        clauses.append("(:country='All markets' OR country=:country)")
    for index, local_filter in enumerate(local_filters):
        if local_filter.dimension not in ds.dimensions:
            continue
        param_name = f"local_{index}"
        clauses.append(f"{ds.dimensions[local_filter.dimension]}=:{param_name}")
        params[param_name] = local_filter.value
    where = " AND ".join(clauses) if clauses else "1=1"
    group = f" GROUP BY {','.join(str(i + 1) for i in range(len(dimensions)))}" if dimensions else ""
    sql = (
        f'SELECT {",".join(dimensions + metrics)} FROM {ds.table} WHERE {where}{group} '
        f'ORDER BY "{plan.order_metric}" {plan.order_direction} LIMIT {plan.limit}'
    )
    return sql, params


def run_widget_query(ctx, widget: Widget, dashboard: Dashboard | None = None) -> WidgetResult:
    plan = _build_plan(widget)
    if plan is None:
        raise WidgetDataError("Select a data domain and at least one measure to render this widget.")
    sql, extra = _compile(plan, effective_filters(dashboard, widget))
    try:
        frame = ctx.query(sql, extra)
    except (SQLQueryError, DataConnectionError) as exc:
        raise WidgetDataError("This widget's query could not be completed. Please retry shortly.") from exc
    ds = DATASETS[plan.dataset]
    labels = {name: ds.metrics[name].label for name in plan.metrics}
    frame = frame.rename(columns=labels)
    dimension_label = plan.dimensions[0].replace("_", " ").title() if plan.dimensions else None
    return WidgetResult(frame=frame, dimension_label=dimension_label, measure_labels=list(labels.values()))


def run_kpi_query(ctx, widget: Widget, dashboard: Dashboard | None = None) -> tuple[float | None, float | None, str]:
    """Returns (current_value, previous_value, measure_label) for a single-measure KPI card,
    aggregated across the full filtered scope (no breakdown)."""
    if not widget.dataset or widget.dataset not in DATASETS or not widget.measures:
        raise WidgetDataError("Select a data domain and a measure to render this KPI.")
    measure = widget.measures[0]
    ds = DATASETS[widget.dataset]
    if measure not in ds.metrics:
        raise WidgetDataError("This measure is not available in the selected data domain.")
    plan = validate_plan(QueryPlan(widget.dataset, (), (measure,), measure, "DESC", 1, "table"))
    if plan is None:
        raise WidgetDataError("This measure could not be validated against the governed catalogue.")
    sql, extra = _compile(plan, effective_filters(dashboard, widget))
    try:
        current = ctx.query(sql, extra)
        previous = ctx.previous_query(sql, extra) if widget.comparison == "previous_period" and ds.date_field else None
    except (SQLQueryError, DataConnectionError) as exc:
        raise WidgetDataError("This KPI's query could not be completed. Please retry shortly.") from exc
    current_value = current.iloc[0][measure] if not current.empty else None
    previous_value = previous.iloc[0][measure] if previous is not None and not previous.empty else None
    return current_value, previous_value, ds.metrics[measure].label
