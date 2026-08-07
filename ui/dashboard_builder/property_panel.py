from __future__ import annotations

"""Right-hand configuration panel for the currently-selected widget: DATA / STYLE / FORMAT tabs,
matching the Tableau/Power BI mental model from the product spec. INTERACTIONS (cross-filter,
drill-down) is intentionally not shown here yet — it isn't wired up, and a tab that does nothing
would be exactly the "fake button" the spec explicitly forbids."""

import streamlit as st

from dashboard_builder.models import LocalFilter, Widget, WIDGET_TYPE_LABELS
from dashboard_builder.query_engine import dataset_choices, dimension_choices, distinct_values, measure_choices
from ui.dashboard_builder import state

NO_BREAKDOWN = "— No breakdown —"
MAX_MEASURES = {"kpi": 1, "pie": 1, "scatter": 2, "line": 3, "bar": 3, "table": 3}


def render_property_panel(ctx, dashboard) -> None:
    widget_id = state.selected_widget_id()
    if widget_id is None:
        st.caption("Select a widget on the canvas (⋮ menu → Edit) to configure it here.")
        return
    widget = next((w for w in dashboard.widgets if w.id == widget_id), None)
    if widget is None:
        state.select_widget(None)
        return

    head, close = st.columns([4, 1])
    with head:
        st.markdown(f"#### {WIDGET_TYPE_LABELS.get(widget.type, widget.type)}")
    with close:
        if st.button("", icon=":material/close:", key="close_property_panel", width="stretch"):
            state.select_widget(None)
            st.rerun()

    if widget.type == "text":
        _render_text_tab(dashboard, widget)
        return

    data_tab, style_tab, format_tab = st.tabs(["Data", "Style", "Format"])
    with data_tab:
        _render_data_tab(ctx, dashboard, widget)
    with style_tab:
        _render_style_tab(dashboard, widget)
    with format_tab:
        _render_format_tab(dashboard, widget)


def _apply(dashboard, changed: bool) -> None:
    if changed:
        state.mark_dirty()
        st.rerun()


def _render_text_tab(dashboard, widget: Widget) -> None:
    content = st.text_area("Markdown content", value=widget.text_content, height=160, key=f"text_content_{widget.id}")
    if content != widget.text_content:
        state.snapshot_for_undo()
        widget.text_content = content
        _apply(dashboard, True)
    title = st.text_input("Widget title (internal label only)", value=widget.title, key=f"text_title_{widget.id}")
    if title != widget.title:
        state.snapshot_for_undo()
        widget.title = title
        _apply(dashboard, True)


def _render_data_tab(ctx, dashboard, widget: Widget) -> None:
    datasets = dataset_choices()
    dataset_keys = list(datasets)
    current_index = dataset_keys.index(widget.dataset) if widget.dataset in dataset_keys else 0
    dataset = st.selectbox("Data domain", dataset_keys, index=current_index, format_func=lambda key: datasets[key], key=f"dataset_{widget.id}")
    if dataset != widget.dataset:
        state.snapshot_for_undo()
        widget.dataset = dataset
        widget.dimension = None
        widget.measures = []
        widget.filters = []
        _apply(dashboard, True)
        return

    dims = dimension_choices(dataset)
    if widget.type != "kpi":
        options = [NO_BREAKDOWN, *dims]
        current = widget.dimension if widget.dimension in dims else NO_BREAKDOWN
        dimension = st.selectbox("Breakdown by", options, index=options.index(current), format_func=lambda key: key if key == NO_BREAKDOWN else dims[key], key=f"dimension_{widget.id}")
        new_dimension = None if dimension == NO_BREAKDOWN else dimension
        if new_dimension != widget.dimension:
            state.snapshot_for_undo()
            widget.dimension = new_dimension
            _apply(dashboard, True)

    measures_map = measure_choices(dataset)
    max_measures = MAX_MEASURES.get(widget.type, 3)
    valid_measures = [m for m in widget.measures if m in measures_map]
    measures = st.multiselect(
        f"Measures (1 to {max_measures})", list(measures_map), default=valid_measures,
        format_func=lambda key: measures_map[key], max_selections=max_measures, key=f"measures_{widget.id}",
    )
    if measures != widget.measures:
        state.snapshot_for_undo()
        widget.measures = measures
        _apply(dashboard, True)

    if widget.type == "kpi" and widget.dataset:
        comparison_options = {"none": "None", "previous_period": "vs previous period"}
        current_comparison = st.selectbox("Comparison", list(comparison_options), index=list(comparison_options).index(widget.comparison), format_func=lambda k: comparison_options[k], key=f"comparison_{widget.id}")
        if current_comparison != widget.comparison:
            state.snapshot_for_undo()
            widget.comparison = current_comparison
            _apply(dashboard, True)

    if widget.type in ("bar", "line", "table") and widget.measures:
        sort_col, topn_col = st.columns(2)
        with sort_col:
            sort_options = {"desc": "Descending", "asc": "Ascending"}
            new_sort = st.selectbox("Sort", list(sort_options), index=list(sort_options).index(widget.sort_direction), format_func=lambda k: sort_options[k], key=f"sort_{widget.id}")
            if new_sort != widget.sort_direction:
                state.snapshot_for_undo()
                widget.sort_direction = new_sort
                _apply(dashboard, True)
        with topn_col:
            new_top_n = st.select_slider("Top N", options=[5, 10, 20, 50, 100], value=widget.top_n or 10, key=f"topn_{widget.id}")
            if new_top_n != widget.top_n:
                state.snapshot_for_undo()
                widget.top_n = new_top_n
                _apply(dashboard, True)

    _render_local_filters(ctx, dashboard, widget, dims)


def _render_local_filters(ctx, dashboard, widget: Widget, dims: dict) -> None:
    st.markdown("**Local filters**")
    if widget.filters:
        for index, local_filter in enumerate(widget.filters):
            row, remove = st.columns([4, 1])
            label = dims.get(local_filter.dimension, local_filter.dimension)
            with row:
                st.caption(f"{label} = {local_filter.value}")
            with remove:
                if st.button("", icon=":material/close:", key=f"remove_filter_{widget.id}_{index}", width="stretch"):
                    state.snapshot_for_undo()
                    widget.filters.pop(index)
                    _apply(dashboard, True)
    else:
        st.caption("No local filters. Only affects this widget.")

    if not dims:
        return
    with st.popover("+ Add local filter", width="stretch"):
        filter_dim = st.selectbox("Field", list(dims), format_func=lambda key: dims[key], key=f"new_filter_dim_{widget.id}")
        values = distinct_values(ctx, widget.dataset, filter_dim) if widget.dataset else []
        if values:
            filter_value = st.selectbox("Value", values, key=f"new_filter_value_{widget.id}")
            if st.button("Add filter", key=f"add_filter_{widget.id}", type="primary", width="stretch"):
                state.snapshot_for_undo()
                widget.filters.append(LocalFilter(dimension=filter_dim, value=filter_value))
                _apply(dashboard, True)
        else:
            st.caption("No values available for this field yet.")


def _render_style_tab(dashboard, widget: Widget) -> None:
    title = st.text_input("Title", value=widget.title, key=f"title_{widget.id}")
    if title != widget.title:
        state.snapshot_for_undo()
        widget.title = title
        _apply(dashboard, True)

    show_title = st.toggle("Show title", value=widget.show_title, key=f"show_title_{widget.id}")
    if show_title != widget.show_title:
        state.snapshot_for_undo()
        widget.show_title = show_title
        _apply(dashboard, True)

    if widget.type in ("line", "bar", "pie", "scatter", "kpi"):
        use_custom = widget.accent_color is not None
        custom = st.checkbox("Custom accent color", value=use_custom, key=f"use_color_{widget.id}")
        if custom:
            color = st.color_picker("Accent color", value=widget.accent_color or "#26c6e5", key=f"color_{widget.id}")
            if color != widget.accent_color:
                state.snapshot_for_undo()
                widget.accent_color = color
                _apply(dashboard, True)
        elif widget.accent_color is not None:
            state.snapshot_for_undo()
            widget.accent_color = None
            _apply(dashboard, True)


def _render_format_tab(dashboard, widget: Widget) -> None:
    compact = st.toggle("Compact notation (K / M / B)", value=widget.compact_numbers, key=f"compact_{widget.id}")
    if compact != widget.compact_numbers:
        state.snapshot_for_undo()
        widget.compact_numbers = compact
        _apply(dashboard, True)
