from __future__ import annotations

"""Dashboard-level global filters — beyond the app-wide date range and market already in the
sidebar (which every widget already respects via SQLContext) — applied to every widget whose
data domain has the matching dimension. A widget's own local filter on the same dimension always
wins (see query_engine.effective_filters)."""

import streamlit as st

from dashboard_builder.models import GlobalFilter
from dashboard_builder.query_engine import dataset_choices, dimension_choices, distinct_values
from ui.dashboard_builder import state


def render_filters_bar(ctx, dashboard) -> None:
    if not dashboard.global_filters and state.mode() == "view":
        return
    st.markdown("<div class='db-filters-label'>DASHBOARD FILTERS</div>", unsafe_allow_html=True)
    chips = st.columns([1] * max(len(dashboard.global_filters), 1) + ([1] if state.mode() == "edit" else []))

    for index, global_filter in enumerate(dashboard.global_filters):
        with chips[index]:
            dims = dimension_choices(global_filter.dataset)
            label = dims.get(global_filter.dimension, global_filter.dimension)
            with st.popover(f"{label} = {global_filter.values[0]}" if global_filter.values else label, width="stretch"):
                st.caption(f"Applies to every {global_filter.dataset} widget without its own local override.")
                if st.button("Remove filter", key=f"remove_global_filter_{index}", width="stretch"):
                    state.snapshot_for_undo()
                    dashboard.global_filters.pop(index)
                    state.mark_dirty()
                    st.rerun()

    if state.mode() == "edit":
        with chips[-1]:
            with st.popover("+ Filter", width="stretch"):
                datasets = dataset_choices()
                dataset = st.selectbox("Data domain", list(datasets), format_func=lambda key: datasets[key], key="new_global_filter_dataset")
                dims = dimension_choices(dataset)
                if not dims:
                    st.caption("No filterable fields for this domain.")
                    return
                dimension = st.selectbox("Field", list(dims), format_func=lambda key: dims[key], key="new_global_filter_dim")
                values = distinct_values(ctx, dataset, dimension)
                if not values:
                    st.caption("No values available yet.")
                    return
                value = st.selectbox("Value", values, key="new_global_filter_value")
                if st.button("Add dashboard filter", type="primary", key="add_global_filter", width="stretch"):
                    state.snapshot_for_undo()
                    dashboard.global_filters.append(GlobalFilter(dimension=dimension, dataset=dataset, values=[value]))
                    state.mark_dirty()
                    st.rerun()
