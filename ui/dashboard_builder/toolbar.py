from __future__ import annotations

"""Top toolbar: dashboard identity, save/undo/redo/mode actions, and live status (last saved,
unsaved changes, current global scope). "Share" from the product spec is intentionally not
rendered — there is nothing behind it yet, and a button that does nothing is worse than no
button. "Full Screen" is implemented honestly as a real, working focus mode (hides the side
panels for more canvas room) rather than a browser fullscreen call Streamlit can't reliably
trigger without a fragile JS hack."""

import json

import streamlit as st

from dashboard_builder import persistence
from dashboard_builder.models import Dashboard
from ui.dashboard_builder import state
from ui.dashboard_builder.identity import tenant_id, user_id

FOCUS_MODE_KEY = "db_focus_mode"


def is_focus_mode() -> bool:
    return st.session_state.get(FOCUS_MODE_KEY, False)


def render_switcher(dashboard: Dashboard) -> None:
    """A quick dashboard switcher available in both Edit and View mode — the full manager
    (rename/duplicate/favorite/default) lives in the left panel's Dashboards tab, only shown in
    Edit mode, but jumping between saved dashboards should always work."""
    saved = persistence.list_dashboards(tenant_id())
    if not saved:
        return
    names = {d.id: d.name for d in saved}
    if dashboard.id not in names:
        names = {dashboard.id: f"{dashboard.name} (unsaved)", **names}
    selected = st.selectbox(
        "Switch dashboard", list(names), index=list(names).index(dashboard.id),
        format_func=lambda key: names[key], key=f"switcher_{dashboard.id}", label_visibility="collapsed",
    )
    if selected != dashboard.id:
        target = next(d for d in saved if d.id == selected)
        state.open_dashboard(target, persisted=True)
        st.rerun()


def render_toolbar(ctx, dashboard: Dashboard) -> None:
    switch_col, name_col, status_col = st.columns([1.6, 2, 2.4])
    with switch_col:
        render_switcher(dashboard)
    with name_col:
        new_name = st.text_input("Dashboard name", value=dashboard.name, key=f"name_{dashboard.id}", label_visibility="collapsed")
        if new_name != dashboard.name:
            dashboard.name = new_name or "Untitled dashboard"
            state.mark_dirty()
    with status_col:
        dirty_badge = "<span class='db-badge db-badge-warn'>Unsaved changes</span>" if state.is_dirty() else f"<span class='db-badge'>{state.last_saved_label()}</span>"
        st.markdown(
            f"<div class='db-status-line'>{dirty_badge}"
            f"<span>{ctx.period_label}</span></div>",
            unsafe_allow_html=True,
        )

    # Two shorter rows instead of one 11-wide row: 11 equal columns squeezed the longer labels
    # ("Duplicate", "Refresh") below their own text width on common laptop screens (~1440px),
    # wrapping them mid-word ("Dupli-cate"). Splitting by purpose (document actions vs.
    # edit/view actions) roughly doubles the room each button gets.
    document_cols = st.columns(5)
    document_actions = [
        ("New", "add_box"), ("Save", "save"), ("Save As", "save_as"),
        ("Duplicate", "content_copy"), ("Delete", "delete"),
    ]
    for col, (label, icon) in zip(document_cols, document_actions):
        with col:
            clicked = st.button(label, key=f"toolbar_{label}_{dashboard.id}", icon=f":material/{icon}:", width="stretch")
        if clicked:
            _handle_action(label, ctx, dashboard)

    edit_cols = st.columns(6)
    edit_actions = [
        ("Undo", "undo"), ("Redo", "redo"), ("Refresh", "refresh"), ("Export", "download"),
        ("Edit" if state.mode() == "view" else "View", "visibility"),
        ("Focus" if not is_focus_mode() else "Exit focus", "fullscreen"),
    ]
    for col, (label, icon) in zip(edit_cols, edit_actions):
        with col:
            clicked = st.button(label, key=f"toolbar_{label}_{dashboard.id}", icon=f":material/{icon}:", width="stretch",
                                 disabled=(label == "Undo" and not state.can_undo()) or (label == "Redo" and not state.can_redo()))
        if clicked:
            _handle_action(label, ctx, dashboard)


def _handle_action(label: str, ctx, dashboard: Dashboard) -> None:
    if label == "New":
        fresh = Dashboard(tenant_id=tenant_id(), user_id=user_id(), name="Untitled dashboard")
        state.open_dashboard(fresh)
    elif label == "Save":
        state.save(dashboard)
    elif label == "Save As":
        st.session_state["db_show_save_as"] = True
    elif label == "Duplicate":
        clone = dashboard.clone(f"{dashboard.name} (copy)", tenant_id(), user_id())
        persistence.save_dashboard(clone)
        state.open_dashboard(clone, persisted=True)
    elif label == "Delete":
        st.session_state["db_show_delete_confirm"] = True
    elif label == "Undo":
        state.undo()
    elif label == "Redo":
        state.redo()
    elif label == "Refresh":
        st.cache_data.clear()
    elif label == "Export":
        st.session_state["db_show_export"] = True
    elif label in ("Edit", "View"):
        state.set_mode("view" if state.mode() == "edit" else "edit")
    elif label in ("Focus", "Exit focus"):
        st.session_state[FOCUS_MODE_KEY] = not is_focus_mode()
    st.rerun()


def render_modals(dashboard: Dashboard) -> None:
    if st.session_state.get("db_show_save_as"):
        with st.popover("Save as…", width="stretch"):
            new_name = st.text_input("New dashboard name", value=f"{dashboard.name} (copy)", key="save_as_name")
            confirm, cancel = st.columns(2)
            with confirm:
                if st.button("Save as new dashboard", type="primary", key="confirm_save_as", width="stretch"):
                    clone = dashboard.clone(new_name.strip() or "Untitled dashboard", tenant_id(), user_id())
                    state.save(clone)
                    state.open_dashboard(clone, persisted=True)
                    st.session_state["db_show_save_as"] = False
                    st.rerun()
            with cancel:
                if st.button("Cancel", key="cancel_save_as", width="stretch"):
                    st.session_state["db_show_save_as"] = False
                    st.rerun()

    if st.session_state.get("db_show_delete_confirm"):
        with st.popover("Delete this dashboard?", width="stretch"):
            st.warning(f"“{dashboard.name}” will be permanently deleted.")
            confirm, cancel = st.columns(2)
            with confirm:
                if st.button("Delete", type="primary", key="confirm_delete", width="stretch"):
                    persistence.delete_dashboard(tenant_id(), dashboard.id)
                    remaining = persistence.list_dashboards(tenant_id())
                    if remaining:
                        state.open_dashboard(remaining[0], persisted=True)
                    else:
                        state.open_dashboard(Dashboard(tenant_id=tenant_id(), user_id=user_id(), name="Untitled dashboard"))
                    st.session_state["db_show_delete_confirm"] = False
                    st.rerun()
            with cancel:
                if st.button("Cancel", key="cancel_delete", width="stretch"):
                    st.session_state["db_show_delete_confirm"] = False
                    st.rerun()

    if st.session_state.get("db_show_export"):
        with st.popover("Export dashboard configuration", width="stretch"):
            payload = json.dumps(dashboard.to_dict(), indent=2)
            st.caption("Downloads this dashboard's structure (widgets, positions, filters, style) as JSON.")
            st.download_button("Download JSON", payload, file_name=f"{dashboard.name.lower().replace(' ', '_')}.json", mime="application/json", width="stretch")
            if st.button("Close", key="close_export", width="stretch"):
                st.session_state["db_show_export"] = False
                st.rerun()
