from __future__ import annotations

"""Session-local editing state for the dashboard builder: which Dashboard is open, whether it
has unsaved changes, undo/redo history, and which widget is selected in the property panel.
The Dashboard object itself lives here between reruns; dashboard_builder.persistence is only
touched on explicit Save/Save As/Delete/Duplicate, never on every widget tweak."""

from datetime import datetime

import streamlit as st

from dashboard_builder import persistence
from dashboard_builder.models import Dashboard
from ui.dashboard_builder.identity import tenant_id, user_id

_STATE_KEY = "db_builder_state"
_MAX_HISTORY = 20


def _blank() -> dict:
    return {
        "dashboard": None, "dirty": False, "mode": "edit", "selected_widget": None,
        "undo_stack": [], "redo_stack": [], "last_saved_label": "Not saved yet",
    }


def _state() -> dict:
    if _STATE_KEY not in st.session_state:
        st.session_state[_STATE_KEY] = _blank()
    return st.session_state[_STATE_KEY]


def current() -> Dashboard | None:
    return _state()["dashboard"]


def is_dirty() -> bool:
    return _state()["dirty"]


def mode() -> str:
    return _state()["mode"]


def set_mode(value: str) -> None:
    _state()["mode"] = value


def selected_widget_id() -> str | None:
    return _state()["selected_widget"]


def select_widget(widget_id: str | None) -> None:
    _state()["selected_widget"] = widget_id


def last_saved_label() -> str:
    return _state()["last_saved_label"]


def _persisted_label(dashboard: Dashboard) -> str:
    """A dashboard loaded from persistence was saved in a previous session, so this session's
    "last saved" clock never actually ran for it — showing the hardcoded "Not saved yet"
    default in that case would misreport a dashboard that is, in fact, saved. Derive the label
    from its own updated_at instead."""
    try:
        saved_at = datetime.fromisoformat(dashboard.updated_at)
    except (TypeError, ValueError):
        return "Not saved yet"
    return f"Saved {saved_at:%d %b, %H:%M UTC}"


def ensure_loaded() -> Dashboard:
    """Load the tenant's default dashboard (or its most recent one) on first visit; otherwise
    keep whatever is already being edited in this session."""
    state = _state()
    if state["dashboard"] is not None:
        return state["dashboard"]
    tenant = tenant_id()
    dashboards = persistence.list_dashboards(tenant)
    if dashboards:
        default = next((d for d in dashboards if d.is_default), dashboards[0])
        state["dashboard"] = default
        state["last_saved_label"] = _persisted_label(default)
    else:
        state["dashboard"] = Dashboard(tenant_id=tenant, user_id=user_id(), name="My first dashboard")
    return state["dashboard"]


def open_dashboard(dashboard: Dashboard, *, persisted: bool = False) -> None:
    """`persisted` must be True only when `dashboard` is already saved in the registry (loaded
    from persistence.list_dashboards, or just written by save_dashboard/duplicate_dashboard) —
    otherwise a brand new, never-saved Dashboard's own timestamp (set at construction time)
    would be mistaken for an actual save."""
    state = _state()
    state["dashboard"] = dashboard
    state["dirty"] = False
    state["selected_widget"] = None
    state["undo_stack"] = []
    state["redo_stack"] = []
    state["last_saved_label"] = _persisted_label(dashboard) if persisted else "Not saved yet"


def replace_current(dashboard: Dashboard, *, dirty: bool) -> None:
    state = _state()
    state["dashboard"] = dashboard
    state["dirty"] = dirty


def mark_dirty() -> None:
    _state()["dirty"] = True


def snapshot_for_undo() -> None:
    """Call BEFORE a mutation. Pushes the pre-mutation state so Undo restores it."""
    state = _state()
    if state["dashboard"] is None:
        return
    state["undo_stack"].append(state["dashboard"].to_dict())
    if len(state["undo_stack"]) > _MAX_HISTORY:
        state["undo_stack"].pop(0)
    state["redo_stack"] = []


def can_undo() -> bool:
    return bool(_state()["undo_stack"])


def can_redo() -> bool:
    return bool(_state()["redo_stack"])


def undo() -> None:
    state = _state()
    if not state["undo_stack"] or state["dashboard"] is None:
        return
    state["redo_stack"].append(state["dashboard"].to_dict())
    previous = state["undo_stack"].pop()
    state["dashboard"] = Dashboard.from_dict(previous)
    state["dirty"] = True


def redo() -> None:
    state = _state()
    if not state["redo_stack"] or state["dashboard"] is None:
        return
    state["undo_stack"].append(state["dashboard"].to_dict())
    nxt = state["redo_stack"].pop()
    state["dashboard"] = Dashboard.from_dict(nxt)
    state["dirty"] = True


def save(dashboard: Dashboard) -> None:
    from datetime import timezone
    persistence.save_dashboard(dashboard)
    state = _state()
    state["dashboard"] = dashboard
    state["dirty"] = False
    state["last_saved_label"] = f"Saved {datetime.now(timezone.utc):%H:%M UTC}"
