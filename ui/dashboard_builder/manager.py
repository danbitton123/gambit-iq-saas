from __future__ import annotations

"""Dashboard list: create / open / rename / duplicate / delete / favorite / set default."""

import streamlit as st

from dashboard_builder import persistence
from dashboard_builder.models import Dashboard
from ui.dashboard_builder import state
from ui.dashboard_builder.identity import tenant_id, user_id


def render_manager() -> None:
    st.markdown("#### My dashboards")
    dashboards = persistence.list_dashboards(tenant_id())
    current = state.current()
    if not dashboards:
        st.caption("No saved dashboards yet. Save your current one, or use a template to start faster.")
    for dashboard in dashboards:
        _render_row(dashboard, current)

    st.divider()
    st.caption("Templates")
    _render_templates()


def _render_row(dashboard: Dashboard, current: Dashboard | None) -> None:
    is_open = current is not None and current.id == dashboard.id
    with st.container(border=True):
        head, star = st.columns([5, 1])
        with head:
            marker = " · open" if is_open else ""
            default_marker = " ⭐" if dashboard.is_default else ""
            st.markdown(f"**{dashboard.name}**{default_marker}{marker}")
            owner = "You" if dashboard.user_id == user_id() else dashboard.user_id
            st.caption(f"{owner} · updated {dashboard.updated_at[:10]} · {len(dashboard.widgets)} widgets")
        with star:
            favorite_icon = ":material/star:" if dashboard.is_favorite else ":material/star_border:"
            if st.button("", icon=favorite_icon, key=f"fav_{dashboard.id}", width="stretch"):
                dashboard.is_favorite = not dashboard.is_favorite
                persistence.save_dashboard(dashboard)
                st.rerun()

        open_col, rename_col, dup_col, default_col, del_col = st.columns(5)
        with open_col:
            if st.button("Open", key=f"open_{dashboard.id}", disabled=is_open, width="stretch"):
                state.open_dashboard(dashboard, persisted=True)
                st.rerun()
        with rename_col:
            with st.popover("Rename", width="stretch"):
                new_name = st.text_input("New name", value=dashboard.name, key=f"rename_input_{dashboard.id}")
                if st.button("Save name", key=f"rename_save_{dashboard.id}", type="primary", width="stretch"):
                    dashboard.name = new_name.strip() or dashboard.name
                    persistence.save_dashboard(dashboard)
                    if is_open:
                        state.replace_current(dashboard, dirty=False)
                    st.rerun()
        with dup_col:
            if st.button("Duplicate", key=f"manager_dup_{dashboard.id}", width="stretch"):
                clone = persistence.duplicate_dashboard(tenant_id(), user_id(), dashboard.id, f"{dashboard.name} (copy)")
                state.open_dashboard(clone, persisted=True)
                st.rerun()
        with default_col:
            if st.button("Set default" if not dashboard.is_default else "Default ✓", key=f"default_{dashboard.id}", disabled=dashboard.is_default, width="stretch"):
                dashboard.is_default = True
                persistence.save_dashboard(dashboard)
                st.rerun()
        with del_col:
            if st.button("Delete", key=f"manager_del_{dashboard.id}", width="stretch"):
                persistence.delete_dashboard(tenant_id(), dashboard.id)
                if is_open:
                    remaining = persistence.list_dashboards(tenant_id())
                    if remaining:
                        state.open_dashboard(remaining[0], persisted=True)
                    else:
                        state.open_dashboard(Dashboard(tenant_id=tenant_id(), user_id=user_id(), name="Untitled dashboard"))
                st.rerun()


def _render_templates() -> None:
    from dashboard_builder.templates import TEMPLATES, auto_generate, build_from_template

    if st.button("✨ Generate Dashboard", key="auto_generate", width="stretch", type="primary"):
        generated = auto_generate(tenant_id(), user_id())
        state.open_dashboard(generated)
        st.rerun()
    st.caption("Assembles governed casino-performance metrics automatically.")

    for key, (name, _builder) in TEMPLATES.items():
        if st.button(name, key=f"template_{key}", width="stretch"):
            dashboard = build_from_template(key, tenant_id(), user_id())
            state.open_dashboard(dashboard)
            st.rerun()
