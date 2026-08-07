from __future__ import annotations

"""Renders the dashboard grid. Widget position/size changes use compact stepper controls
(◀▲▼▶ move, size +/-) rather than mouse drag: streamlit-elements, the community's usual
react-grid-layout wrapper for this, hasn't shipped a release since 2022 and its compatibility
with current Streamlit is unverified — exactly the "fragile, unmaintained dependency" this
project's own constraints rule out. Every control here still moves/resizes/persists for real; a
future maintained drag-and-drop component can replace just this file without touching the data
model (Widget.x/y/w/h) or anything downstream."""

import streamlit as st

from dashboard_builder.layout import move_widget, next_position, pack_rows, resize_widget
from dashboard_builder.models import WIDGET_TYPE_ICONS, Widget, new_id
from ui.dashboard_builder import state
from ui.dashboard_builder.widget_render import render_widget_content


def render_canvas(ctx) -> None:
    dashboard = state.current()
    if dashboard is None:
        return
    if not dashboard.widgets:
        _empty_canvas()
        return
    edit = state.mode() == "edit"
    for row in pack_rows(dashboard.widgets):
        cols = st.columns([widget.w for widget in row])
        for col, widget in zip(cols, row):
            with col:
                _render_card(ctx, dashboard, widget, edit)


def _empty_canvas() -> None:
    st.markdown(
        "<div class='db-empty-canvas'><span class='material-symbols-rounded'>dashboard_customize</span>"
        "<strong>This dashboard is empty</strong><p>Add a visualization from the left panel to get started.</p></div>",
        unsafe_allow_html=True,
    )


def _render_card(ctx, dashboard, widget: Widget, edit: bool) -> None:
    selected = state.selected_widget_id() == widget.id
    with st.container(border=True):
        if edit:
            _card_toolbar(dashboard, widget, selected)
        elif widget.show_title and widget.type != "text":
            st.caption(widget.title)
        render_widget_content(ctx, widget, dashboard)


def _card_toolbar(dashboard, widget: Widget, selected: bool) -> None:
    head, menu = st.columns([5, 1])
    with head:
        icon = WIDGET_TYPE_ICONS.get(widget.type, "widgets")
        marker = " 🟢" if selected else ""
        st.markdown(f"<span class='material-symbols-rounded db-widget-icon'>{icon}</span> **{widget.title}**{marker}", unsafe_allow_html=True)
    with menu:
        with st.popover("⋮", width="stretch"):
            _widget_menu(dashboard, widget)


def _widget_menu(dashboard, widget: Widget) -> None:
    st.caption(f"{widget.type.upper()} · {widget.w}×{widget.h}")
    edit_col, dup_col, del_col = st.columns(3)
    with edit_col:
        if st.button("Edit", key=f"edit_{widget.id}", icon=":material/tune:", width="stretch"):
            state.select_widget(widget.id)
            st.rerun()
    with dup_col:
        if st.button("Duplicate", key=f"dup_{widget.id}", icon=":material/content_copy:", width="stretch"):
            state.snapshot_for_undo()
            clone = Widget.from_dict(widget.to_dict())
            clone.id = new_id()
            clone.title = f"{widget.title} (copy)"
            clone.y, clone.x = next_position(dashboard.widgets, clone.w)
            dashboard.widgets.append(clone)
            state.mark_dirty()
            st.rerun()
    with del_col:
        if st.button("Delete", key=f"del_{widget.id}", icon=":material/delete:", width="stretch"):
            state.snapshot_for_undo()
            dashboard.widgets = [w for w in dashboard.widgets if w.id != widget.id]
            if state.selected_widget_id() == widget.id:
                state.select_widget(None)
            state.mark_dirty()
            st.rerun()

    st.caption("Move")
    left, up, down, right = st.columns(4)
    for col, direction, icon in ((left, "left", "arrow_back"), (up, "up", "arrow_upward"), (down, "down", "arrow_downward"), (right, "right", "arrow_forward")):
        with col:
            if st.button("", key=f"move_{direction}_{widget.id}", icon=f":material/{icon}:", width="stretch"):
                state.snapshot_for_undo()
                move_widget(dashboard.widgets, widget.id, direction)
                state.mark_dirty()
                st.rerun()

    st.caption("Size")
    w_minus, w_label, w_plus, h_minus, h_label, h_plus = st.columns(6)
    with w_minus:
        if st.button("", key=f"w_minus_{widget.id}", icon=":material/remove:", width="stretch"):
            state.snapshot_for_undo(); resize_widget(widget, delta_w=-1); state.mark_dirty(); st.rerun()
    with w_label:
        st.markdown(f"<div class='db-size-label'>W {widget.w}</div>", unsafe_allow_html=True)
    with w_plus:
        if st.button("", key=f"w_plus_{widget.id}", icon=":material/add:", width="stretch"):
            state.snapshot_for_undo(); resize_widget(widget, delta_w=1); state.mark_dirty(); st.rerun()
    with h_minus:
        if st.button("", key=f"h_minus_{widget.id}", icon=":material/remove:", width="stretch"):
            state.snapshot_for_undo(); resize_widget(widget, delta_h=-1); state.mark_dirty(); st.rerun()
    with h_label:
        st.markdown(f"<div class='db-size-label'>H {widget.h}</div>", unsafe_allow_html=True)
    with h_plus:
        if st.button("", key=f"h_plus_{widget.id}", icon=":material/add:", width="stretch"):
            state.snapshot_for_undo(); resize_widget(widget, delta_h=1); state.mark_dirty(); st.rerun()
