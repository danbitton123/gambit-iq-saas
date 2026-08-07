from __future__ import annotations

"""Left panel: quick "add a visualization" flow, and a searchable reference of the fields
available in each governed data domain. True field-to-shelf drag-and-drop (GGR → Y Axis) is the
one place this build deliberately follows the spec's own fallback clause and uses clean
selectors instead — the widget canvas keeps real, working move/resize/duplicate/delete."""

import streamlit as st

from dashboard_builder.layout import next_position
from dashboard_builder.models import DEFAULT_SIZE, WIDGET_TYPE_LABELS, WIDGET_TYPES, Widget
from dashboard_builder.query_engine import dataset_choices, dimension_choices, measure_choices
from ui.dashboard_builder import state

MAX_MEASURES = {"kpi": 1, "pie": 1, "scatter": 2, "line": 3, "bar": 3, "table": 3}
NO_BREAKDOWN = "— No breakdown —"


def render_add_visualization(dashboard) -> None:
    st.markdown("#### Add visualization")
    with st.form(f"add_widget_form_{dashboard.id}", border=True):
        widget_type = st.selectbox("Type", WIDGET_TYPES, format_func=lambda key: WIDGET_TYPE_LABELS[key])
        if widget_type == "text":
            content = st.text_area("Text (markdown)", placeholder="## Casino Performance Overview\n\nUpdated daily.", height=100)
            submitted = st.form_submit_button("Add to dashboard", icon=":material/add:", type="primary", width="stretch")
            if submitted:
                _add_widget(dashboard, widget_type, text_content=content)
            return

        datasets = dataset_choices()
        dataset = st.selectbox("Data domain", list(datasets), format_func=lambda key: datasets[key])
        dims = dimension_choices(dataset)
        dimension = None
        if widget_type != "kpi":
            options = [NO_BREAKDOWN, *dims]
            choice = st.selectbox("Breakdown by", options, format_func=lambda key: key if key == NO_BREAKDOWN else dims[key])
            dimension = None if choice == NO_BREAKDOWN else choice
        measures_map = measure_choices(dataset)
        max_measures = MAX_MEASURES.get(widget_type, 3)
        measures = st.multiselect(f"Measures (1 to {max_measures})", list(measures_map), format_func=lambda key: measures_map[key], max_selections=max_measures)
        submitted = st.form_submit_button("Add to dashboard", icon=":material/add:", type="primary", width="stretch")
        if submitted:
            if not measures:
                st.error("Select at least one measure.")
            else:
                _add_widget(dashboard, widget_type, dataset=dataset, dimension=dimension, measures=measures)


def _add_widget(dashboard, widget_type: str, **kwargs) -> None:
    state.snapshot_for_undo()
    width, height = DEFAULT_SIZE.get(widget_type, (4, 4))
    y, x = next_position(dashboard.widgets, width)
    widget = Widget(type=widget_type, title=_default_title(widget_type, kwargs), x=x, y=y, w=width, h=height, **kwargs)
    dashboard.widgets.append(widget)
    state.select_widget(widget.id)
    state.mark_dirty()
    st.rerun()


def _default_title(widget_type: str, kwargs: dict) -> str:
    if widget_type == "text":
        return "Text"
    dataset = kwargs.get("dataset")
    measures = kwargs.get("measures") or []
    if not dataset or not measures:
        return f"New {WIDGET_TYPE_LABELS[widget_type]}"
    measure_label = measure_choices(dataset).get(measures[0], measures[0])
    dimension = kwargs.get("dimension")
    if dimension:
        dimension_label = dimension_choices(dataset).get(dimension, dimension)
        return f"{measure_label} by {dimension_label}"
    return measure_label


def render_field_browser() -> None:
    st.markdown("#### Fields")
    st.caption("Reference of the governed dimensions and measures available per data domain.")
    datasets = dataset_choices()
    dataset = st.selectbox("Data domain", list(datasets), format_func=lambda key: datasets[key], key="field_browser_dataset")
    query = st.text_input("Search fields...", key="field_browser_search", placeholder="GGR, country, deposit…")
    needle = query.strip().lower()

    dims = dimension_choices(dataset)
    measures = measure_choices(dataset)
    filtered_dims = {k: v for k, v in dims.items() if not needle or needle in v.lower()}
    filtered_measures = {k: v for k, v in measures.items() if not needle or needle in v.lower()}

    with st.expander(f"Dimensions ({len(filtered_dims)})", expanded=bool(needle)):
        if not filtered_dims:
            st.caption("No matching dimension.")
        for label in filtered_dims.values():
            st.markdown(f"<div class='db-field-row'><span class='material-symbols-rounded'>tag</span>{label}</div>", unsafe_allow_html=True)
    with st.expander(f"Measures ({len(filtered_measures)})", expanded=bool(needle)):
        if not filtered_measures:
            st.caption("No matching measure.")
        for label in filtered_measures.values():
            st.markdown(f"<div class='db-field-row'><span class='material-symbols-rounded'>function</span>{label}</div>", unsafe_allow_html=True)
