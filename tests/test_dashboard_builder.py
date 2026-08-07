from __future__ import annotations

"""Tests for the My Dashboard BI builder (dashboard_builder/ + ui/dashboard_builder/).

Covers the mandated test list: dashboard CRUD, widget CRUD/move/resize, global+local filters,
KPI parity against other governed pages (no silent divergence), tenant isolation, invalid/empty
data handling, and layout persistence."""

import re
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard_builder import layout, persistence, templates, validation
from dashboard_builder.models import Dashboard, GlobalFilter, LocalFilter, Widget, WIDGET_TYPES
from dashboard_builder.query_engine import (
    WidgetDataError, dataset_choices, dimension_choices, effective_filters,
    measure_choices, run_kpi_query, run_widget_query,
)
from data.repository import SQLContext, SQLRepository
from queries.overview import performance_summary

HARNESS = Path(__file__).resolve().parent / "app_harness.py"


def _ctx(start="2026-05-01", end="2026-05-31", country="All markets") -> SQLContext:
    return SQLContext(repo=SQLRepository(), start=pd.Timestamp(start), end=pd.Timestamp(end), country=country)


# ---------------------------------------------------------------------------
# Models: serialization round-trip
# ---------------------------------------------------------------------------

def test_widget_round_trips_through_dict():
    widget = Widget(
        type="bar", title="GGR by Country", x=3, y=1, w=6, h=5, dataset="executive",
        dimension="country", measures=["ggr", "deposits"], filters=[LocalFilter("country", "Canada")],
        accent_color="#26c6e5",
    )
    restored = Widget.from_dict(widget.to_dict())
    assert restored == widget


def test_dashboard_round_trips_through_dict_including_widgets_and_filters():
    dashboard = Dashboard(
        tenant_id="Northstar Bay Casino", user_id="user-1", name="Exec View",
        widgets=[Widget(type="kpi", dataset="executive", measures=["ggr"])],
        global_filters=[GlobalFilter(dimension="country", dataset="executive", values=["Canada"])],
    )
    restored = Dashboard.from_dict(dashboard.to_dict())
    assert restored.name == dashboard.name
    assert len(restored.widgets) == 1
    assert restored.global_filters[0].values == ["Canada"]


def test_dashboard_clone_generates_new_widget_ids():
    original = Dashboard(tenant_id="t1", user_id="u1", name="Original", widgets=[Widget(dataset="executive", measures=["ggr"])])
    clone = original.clone("Copy", "t1", "u1")
    assert clone.id != original.id
    assert clone.widgets[0].id != original.widgets[0].id
    assert clone.name == "Copy"


# ---------------------------------------------------------------------------
# Persistence: create/load/save/delete/duplicate + tenant isolation
# ---------------------------------------------------------------------------

@pytest.fixture()
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "REGISTRY_PATH", tmp_path / "dashboards.db")
    return persistence


def test_dashboard_create_save_load_round_trip(registry):
    dashboard = Dashboard(tenant_id="Tenant A", user_id="u1", name="My board", widgets=[Widget(dataset="executive", measures=["ggr"])])
    registry.save_dashboard(dashboard)
    loaded = registry.load_dashboard("Tenant A", dashboard.id)
    assert loaded.name == "My board"
    assert loaded.widgets[0].dataset == "executive"


def test_dashboard_list_orders_and_delete(registry):
    first = Dashboard(tenant_id="Tenant A", user_id="u1", name="First")
    second = Dashboard(tenant_id="Tenant A", user_id="u1", name="Second")
    registry.save_dashboard(first)
    registry.save_dashboard(second)
    assert {d.name for d in registry.list_dashboards("Tenant A")} == {"First", "Second"}

    registry.delete_dashboard("Tenant A", first.id)
    remaining = registry.list_dashboards("Tenant A")
    assert len(remaining) == 1 and remaining[0].name == "Second"


def test_dashboard_duplicate_creates_independent_copy(registry):
    original = Dashboard(tenant_id="Tenant A", user_id="u1", name="Original", widgets=[Widget(dataset="executive", measures=["ggr"])])
    registry.save_dashboard(original)
    clone = registry.duplicate_dashboard("Tenant A", "u1", original.id, "Original (copy)")
    assert clone.id != original.id
    assert clone.widgets[0].id != original.widgets[0].id
    reloaded_original = registry.load_dashboard("Tenant A", original.id)
    assert reloaded_original.name == "Original"  # unaffected by the duplicate


def test_save_default_dashboard_clears_previous_default(registry):
    first = Dashboard(tenant_id="Tenant A", user_id="u1", name="First", is_default=True)
    second = Dashboard(tenant_id="Tenant A", user_id="u1", name="Second", is_default=True)
    registry.save_dashboard(first)
    registry.save_dashboard(second)
    assert registry.default_dashboard_id("Tenant A") == second.id
    assert registry.load_dashboard("Tenant A", first.id).is_default is False


def test_tenant_cannot_load_or_delete_another_tenants_dashboard_even_by_forged_id(registry):
    victim = Dashboard(tenant_id="Tenant A", user_id="u1", name="Confidential")
    registry.save_dashboard(victim)

    with pytest.raises(persistence.DashboardNotFoundError):
        registry.load_dashboard("Tenant B", victim.id)  # forged id, wrong tenant

    registry.delete_dashboard("Tenant B", victim.id)  # no-op: scoped WHERE tenant_id=?
    assert registry.load_dashboard("Tenant A", victim.id).name == "Confidential"


def test_tenant_dashboard_lists_never_cross_over(registry):
    registry.save_dashboard(Dashboard(tenant_id="Tenant A", user_id="u1", name="A's board"))
    registry.save_dashboard(Dashboard(tenant_id="Tenant B", user_id="u1", name="B's board"))
    assert [d.name for d in registry.list_dashboards("Tenant A")] == ["A's board"]
    assert [d.name for d in registry.list_dashboards("Tenant B")] == ["B's board"]


# ---------------------------------------------------------------------------
# Layout: move / resize / packing never overlaps
# ---------------------------------------------------------------------------

def test_pack_rows_never_exceeds_twelve_columns_per_row():
    widgets = [Widget(w=6, h=4, y=0, x=0), Widget(w=6, h=4, y=0, x=1), Widget(w=6, h=4, y=0, x=2)]
    rows = layout.pack_rows(widgets)
    assert all(sum(w.w for w in row) <= 12 for row in rows)
    assert sum(len(row) for row in rows) == 3


def test_move_widget_swaps_within_row_and_across_rows():
    a, b = Widget(w=6, h=4, y=0, x=0), Widget(w=6, h=4, y=0, x=1)
    widgets = [a, b]
    layout.move_widget(widgets, b.id, "left")
    assert (a.x, b.x) == (1, 0)

    layout.move_widget(widgets, b.id, "down")
    rows = layout.pack_rows(widgets)
    assert len(rows) == 2 and rows[1][0].id == b.id


def test_resize_widget_respects_min_and_max_bounds():
    widget = Widget(w=2, h=2)
    layout.resize_widget(widget, delta_w=-5, delta_h=-5)
    assert widget.w == layout.MIN_W and widget.h == layout.MIN_H
    widget2 = Widget(w=12, h=10)
    layout.resize_widget(widget2, delta_w=5, delta_h=5)
    assert widget2.w == layout.MAX_W and widget2.h == layout.MAX_H


def test_next_position_wraps_to_new_row_when_full():
    widgets = [Widget(w=8, h=4, y=0, x=0)]
    y, x = layout.next_position(widgets, 6)
    assert (y, x) == (1, 0)  # 8 + 6 > 12, so it wraps
    y2, x2 = layout.next_position(widgets, 4)
    assert (y2, x2) == (0, 1)  # 8 + 4 == 12, fits on the same row


# ---------------------------------------------------------------------------
# Validation: never a fake success, always guidance text on incomplete config
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("widget,expected_substring", [
    (Widget(type="pie", dataset="executive", measures=["ggr"]), "dimension"),
    (Widget(type="line", dataset="executive"), "dimension"),
    (Widget(type="scatter", dataset="executive", measures=["ggr"]), "two measures"),
    (Widget(type="kpi", dataset="executive"), "measure"),
    (Widget(type="text", text_content=""), "text"),
    (Widget(type="table", dataset="executive"), "measure"),
])
def test_validate_widget_returns_actionable_guidance_for_incomplete_configs(widget, expected_substring):
    reason = validation.validate_widget(widget)
    assert reason is not None and expected_substring in reason


def test_validate_widget_accepts_a_complete_configuration():
    widget = Widget(type="bar", dataset="executive", dimension="country", measures=["ggr"])
    assert validation.validate_widget(widget) is None


# ---------------------------------------------------------------------------
# Query engine: dataset/dimension/measure catalogues, filters, error handling
# ---------------------------------------------------------------------------

def test_dataset_choices_includes_every_governed_domain():
    choices = dataset_choices()
    assert "player_activity" in choices
    assert choices["player_activity"] == "Player Activity"


def test_effective_filters_merges_global_and_local_with_local_precedence():
    dashboard = Dashboard(
        tenant_id="t", user_id="u",
        global_filters=[GlobalFilter(dimension="country", dataset="executive", values=["Canada"])],
    )
    widget = Widget(dataset="executive", measures=["ggr"])
    merged = effective_filters(dashboard, widget)
    assert any(f.dimension == "country" and f.value == "Canada" for f in merged)

    widget_with_local = Widget(dataset="executive", measures=["ggr"], filters=[LocalFilter("country", "Germany")])
    merged2 = effective_filters(dashboard, widget_with_local)
    country_filters = [f for f in merged2 if f.dimension == "country"]
    assert country_filters == [LocalFilter("country", "Germany")]  # local wins, not duplicated


def test_effective_filters_ignores_global_filter_from_a_different_dataset():
    dashboard = Dashboard(
        tenant_id="t", user_id="u",
        global_filters=[GlobalFilter(dimension="country", dataset="players", values=["Canada"])],
    )
    widget = Widget(dataset="executive", measures=["ggr"])
    merged = effective_filters(dashboard, widget)
    assert not any(f.dimension == "country" for f in merged)


def test_run_widget_query_on_incomplete_widget_raises_widget_data_error_not_a_crash():
    with pytest.raises(WidgetDataError):
        run_widget_query(_ctx(), Widget(type="bar", dataset=None))


def test_run_kpi_query_with_unknown_measure_raises_widget_data_error():
    with pytest.raises(WidgetDataError):
        run_kpi_query(_ctx(), Widget(type="kpi", dataset="executive", measures=["not_a_real_measure"]))


def test_run_widget_query_returns_empty_frame_gracefully_for_a_narrow_local_filter():
    widget = Widget(
        type="bar", dataset="executive", dimension="country", measures=["ggr"],
        filters=[LocalFilter("country", "Nowhere Land")],
    )
    result = run_widget_query(_ctx(), widget)
    assert result.frame.empty  # renderer turns this into "No data available", never an exception


# ---------------------------------------------------------------------------
# KPI parity: My Dashboard must match Command Center exactly (no silent divergence)
# ---------------------------------------------------------------------------

def _command_center_row(start="2026-05-01", end="2026-05-31", country="All markets"):
    return performance_summary.run(_ctx(start, end, country))


@pytest.mark.parametrize("country", ["All markets", "Canada"])
def test_ggr_matches_command_center(country):
    ctx = _ctx(country=country)
    dashboard_value, _, _ = run_kpi_query(ctx, Widget(type="kpi", dataset="executive", measures=["ggr"]))
    reference = _command_center_row(country=country)
    assert dashboard_value == pytest.approx(reference["ggr"])


@pytest.mark.parametrize("country", ["All markets", "Canada"])
def test_estimated_ngr_matches_command_center(country):
    ctx = _ctx(country=country)
    dashboard_value, _, _ = run_kpi_query(ctx, Widget(type="kpi", dataset="executive", measures=["estimated_ngr"]))
    reference = _command_center_row(country=country)
    assert dashboard_value == pytest.approx(reference["ngr"])


@pytest.mark.parametrize("country", ["All markets", "Canada"])
def test_deposits_matches_command_center(country):
    ctx = _ctx(country=country)
    dashboard_value, _, _ = run_kpi_query(ctx, Widget(type="kpi", dataset="executive", measures=["deposits"]))
    reference = _command_center_row(country=country)
    assert dashboard_value == pytest.approx(reference["deposits"])


@pytest.mark.parametrize("country", ["All markets", "Canada"])
def test_active_players_matches_command_center(country):
    ctx = _ctx(country=country)
    dashboard_value, _, _ = run_kpi_query(ctx, Widget(type="kpi", dataset="player_activity", measures=["active_players"]))
    reference = _command_center_row(country=country)
    assert dashboard_value == pytest.approx(reference["players"])


@pytest.mark.parametrize("country", ["All markets", "Canada"])
def test_ftd_matches_command_center(country):
    ctx = _ctx(country=country)
    dashboard_value, _, _ = run_kpi_query(ctx, Widget(type="kpi", dataset="acquisition", measures=["ftd"]))
    reference = _command_center_row(country=country)
    assert dashboard_value == pytest.approx(reference["ftd"])


def test_ggr_matches_command_center_across_a_period_boundary_day():
    """Regression test for the DATE()-normalization bug: without it, the first day of the
    period was silently dropped from date-only mart columns."""
    ctx = _ctx(start="2026-05-07", end="2026-05-07")
    dashboard_value, _, _ = run_kpi_query(ctx, Widget(type="kpi", dataset="executive", measures=["ggr"]))
    reference = _command_center_row(start="2026-05-07", end="2026-05-07")
    assert dashboard_value == pytest.approx(reference["ggr"])
    assert dashboard_value not in (None, 0)


# ---------------------------------------------------------------------------
# Templates: every prebuilt dashboard is a fully valid, renderable widget set
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("template_key", list(templates.TEMPLATES))
def test_every_template_builds_only_valid_widgets_against_the_real_catalogue(template_key):
    dashboard = templates.build_from_template(template_key, "Tenant A", "u1")
    assert dashboard.widgets
    for widget in dashboard.widgets:
        assert validation.validate_widget(widget) is None
        if widget.dataset:
            assert widget.dataset in dataset_choices()
            for measure in widget.measures:
                assert measure in measure_choices(widget.dataset)
            if widget.dimension:
                assert widget.dimension in dimension_choices(widget.dataset)


def test_casino_executive_performance_template_widgets_render_with_real_data():
    dashboard = templates.build_from_template("casino_executive", "Tenant A", "u1")
    ctx = _ctx()
    for widget in dashboard.widgets:
        if widget.type == "kpi":
            value, _, _ = run_kpi_query(ctx, widget, dashboard)
            assert value is not None
        elif widget.type != "text":
            result = run_widget_query(ctx, widget, dashboard)
            assert result.frame is not None  # may be empty, must never raise


def test_auto_generate_produces_a_named_dashboard_from_the_same_shape():
    dashboard = templates.auto_generate("Tenant A", "u1")
    assert dashboard.name == "Generated Dashboard"
    assert dashboard.widgets


# ---------------------------------------------------------------------------
# Widget type coverage: every declared type has a working smart default title
# ---------------------------------------------------------------------------

def test_every_widget_type_has_a_default_size():
    from dashboard_builder.models import DEFAULT_SIZE
    assert set(DEFAULT_SIZE) == set(WIDGET_TYPES)


# ---------------------------------------------------------------------------
# UI integration: save/reload persistence, theme switching, no console-visible exceptions
# ---------------------------------------------------------------------------

def _status_badge_text(app) -> str:
    html = "\n".join(str(item.value) for item in app.markdown)
    match = re.search(r"db-badge[^>]*>([^<]*)<", html)
    return match.group(1) if match else ""


def test_save_then_reopen_in_a_fresh_session_shows_a_real_saved_label_not_saved_yet(registry):
    """Regression test: a dashboard saved in one browser session must not show "Not saved yet"
    when it is loaded fresh in a new session — state.py derives the label from the persisted
    dashboard's own updated_at instead of trusting the new session's blank default. The
    `registry` fixture points persistence at an isolated tmp_path registry, so this only ever
    sees dashboards this test itself created."""
    first_session = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    first_session = _widget(first_session.radio, "Test page").set_value("My Dashboard").run()
    assert not first_session.exception

    save_button = next(b for b in first_session.button if b.key and b.key.startswith("toolbar_Save_"))
    first_session = save_button.set_value(True).run()
    assert not first_session.exception
    assert "Saved" in _status_badge_text(first_session)

    second_session = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    second_session = _widget(second_session.radio, "Test page").set_value("My Dashboard").run()
    assert not second_session.exception
    badge = _status_badge_text(second_session)
    assert "Saved" in badge and "Not saved yet" not in badge


def _widget(elements, label):
    return next(element for element in elements if element.label == label)


def test_my_dashboard_renders_without_exception_in_light_mode():
    app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    app = _widget(app.radio, "Test page").set_value("My Dashboard").run()
    assert not app.exception
    design_toggle = next((w for w in app.segmented_control if w.label == "Design"), None)
    if design_toggle is not None:
        app = design_toggle.set_value("Light").run()
        assert not app.exception
