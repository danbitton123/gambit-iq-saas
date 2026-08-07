from __future__ import annotations

"""My Dashboard: a self-service BI dashboard builder. Thin orchestration only — every real
concern (data model, persistence, query compilation, layout, rendering) lives under
dashboard_builder/ and ui/dashboard_builder/; see query_engine.py's module docstring for how KPI
parity with the rest of CasinoAI is guaranteed, and canvas.py's for why widget positioning uses
stepper controls instead of mouse drag."""

import streamlit as st

from ui.dashboard_builder import state
from ui.dashboard_builder.canvas import render_canvas
from ui.dashboard_builder.data_panel import render_add_visualization, render_field_browser
from ui.dashboard_builder.filters_bar import render_filters_bar
from ui.dashboard_builder.manager import render_manager
from ui.dashboard_builder.property_panel import render_property_panel
from ui.dashboard_builder.toolbar import is_focus_mode, render_modals, render_toolbar
from ui.theme import page_header


def render(ctx) -> None:
    page_header("MY DASHBOARD", "Build your own dashboards from governed CasinoAI data — no SQL required", "Self-Serve BI")
    dashboard = state.ensure_loaded()

    render_toolbar(ctx, dashboard)
    render_modals(dashboard)
    render_filters_bar(ctx, dashboard)
    st.divider()

    show_panels = state.mode() == "edit" and not is_focus_mode()
    if not show_panels:
        render_canvas(ctx)
        return

    left, center, right = st.columns([1.15, 3.3, 1.25])
    with left:
        build_tab, fields_tab, manage_tab = st.tabs(["Build", "Fields", "Dashboards"])
        with build_tab:
            render_add_visualization(dashboard)
        with fields_tab:
            render_field_browser()
        with manage_tab:
            render_manager()
    with center:
        render_canvas(ctx)
    with right:
        render_property_panel(ctx, dashboard)
