from __future__ import annotations

import streamlit as st

from data.semantic_query import DATASETS, QueryPlan, compile_plan, validate_plan
from ui.charts import bars, line, polish
from ui.components import chart, data_table, empty_state
from ui.theme import page_header

DATASET_LABELS = {
    "executive": "Executive overview", "casino": "Casino", "sportsbook": "Sportsbook",
    "payments": "Payments", "acquisition": "Acquisition", "players": "Players",
}
CHART_TYPES = {"bar": "Bar chart", "line": "Line chart", "table": "Table"}
NO_BREAKDOWN = "— No breakdown —"
SESSION_KEY = "custom_dashboard_charts"
ROW_LIMIT = 25


def _dimension_label(name: str) -> str:
    return name.replace("_", " ").title()


def _render_chart(ctx, spec: dict, index: int) -> None:
    plan = spec["plan"]
    ds = DATASETS[plan.dataset]
    header_left, header_right = st.columns([5, 1])
    with header_left:
        st.markdown(f"**{spec['title']}**")
    with header_right:
        if st.button("Remove", key=f"remove_custom_chart_{index}", icon=":material/close:", width="stretch"):
            st.session_state[SESSION_KEY].pop(index)
            st.rerun()
    try:
        evidence = ctx.query(compile_plan(plan))
    except Exception:
        st.error("This chart could not be computed for the current filters. Try removing it and building it again.")
        return
    labels = {name: ds.metrics[name].label for name in plan.metrics}
    evidence = evidence.rename(columns=labels)
    metric_cols = list(labels.values())
    if evidence.empty:
        empty_state()
        return
    if plan.chart_type == "table":
        data_table(evidence)
        return
    dimension_col = evidence.columns[0] if plan.dimensions else None
    if dimension_col is None:
        totals = evidence.iloc[0][metric_cols].reset_index()
        totals.columns = ["Measure", "Value"]
        fig = bars(totals, x="Measure", y="Value", title=spec["title"].upper())
    elif plan.chart_type == "line":
        fig = line(evidence, x=dimension_col, y=metric_cols, title=spec["title"].upper())
    else:
        fig = bars(evidence, x=dimension_col, y=metric_cols, title=spec["title"].upper())
    chart(polish(fig, 340), evidence)


def render(ctx) -> None:
    page_header("MY DASHBOARD", "Build your own charts and tables from governed data — no SQL required", "Self-Serve Analysis")
    st.caption(
        "Pick a data domain, an optional breakdown and one to three measures, then add the chart to your dashboard. "
        "Every chart runs the same governed, read-only queries as the rest of the site and respects the global date "
        "range and market filters. Your dashboard is kept for this session only."
    )
    st.session_state.setdefault(SESSION_KEY, [])

    # The domain picker lives outside the form so breakdown/measure options update immediately
    # when it changes — inside a form, those dependent widgets would keep showing the previous
    # domain's options until the form was submitted.
    dataset_name = st.selectbox("Data domain", list(DATASETS), format_func=lambda name: DATASET_LABELS[name], key="custom_dashboard_domain")
    dataset = DATASETS[dataset_name]

    with st.form("custom_dashboard_builder"):
        c2, c3 = st.columns(2)
        with c2:
            dimension_choice = st.selectbox("Breakdown by", [NO_BREAKDOWN, *dataset.dimensions], format_func=lambda name: name if name == NO_BREAKDOWN else _dimension_label(name))
        with c3:
            chart_type = st.selectbox("Chart type", list(CHART_TYPES), format_func=lambda key: CHART_TYPES[key])
        metrics = st.multiselect("Measures (1 to 3)", list(dataset.metrics), format_func=lambda name: dataset.metrics[name].label, max_selections=3)
        title = st.text_input("Chart title", placeholder="e.g. GGR by country")
        submitted = st.form_submit_button("Add to my dashboard", icon=":material/add_chart:", type="primary", width="stretch")

    if submitted:
        if not metrics:
            st.error("Choose at least one measure.")
        else:
            dimensions = () if dimension_choice == NO_BREAKDOWN else (dimension_choice,)
            plan = validate_plan(QueryPlan(dataset_name, dimensions, tuple(metrics), metrics[0], "DESC", ROW_LIMIT, chart_type))
            if plan is None:
                st.error("That combination isn't valid. Try different measures or a different breakdown.")
            else:
                default_title = f"{DATASET_LABELS[dataset_name]} — {', '.join(dataset.metrics[m].label for m in metrics)}"
                st.session_state[SESSION_KEY].append({"title": title.strip() or default_title, "plan": plan})
                st.rerun()

    charts = st.session_state[SESSION_KEY]
    if not charts:
        st.info("Your dashboard is empty. Build your first chart above.")
        return

    top_left, top_right = st.columns([5, 1])
    with top_left:
        st.markdown(f"### Your dashboard · {len(charts)} chart{'s' if len(charts) != 1 else ''}")
    with top_right:
        if st.button("Clear all", icon=":material/delete_sweep:", width="stretch"):
            st.session_state[SESSION_KEY] = []
            st.rerun()
    columns = st.columns(2)
    for index, spec in enumerate(charts):
        with columns[index % 2]:
            _render_chart(ctx, spec, index)
