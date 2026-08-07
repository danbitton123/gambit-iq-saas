from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from dashboard_builder import persistence

APP = Path(__file__).resolve().parents[1] / "app.py"
HARNESS = Path(__file__).resolve().parent / "app_harness.py"
CONFIG = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
THEME = Path(__file__).resolve().parents[1] / "ui" / "theme.py"
COMPONENTS = Path(__file__).resolve().parents[1] / "ui" / "components.py"


@pytest.fixture(autouse=True)
def _isolated_dashboard_registry(tmp_path, monkeypatch):
    """My Dashboard loads the tenant's saved dashboards on first visit (see
    ui/dashboard_builder/state.py::ensure_loaded). Pointing every page test at an empty,
    per-test registry keeps these tests hermetic regardless of what a real user (or a manual
    verification session) has actually saved to data/dashboards.db."""
    monkeypatch.setattr(persistence, "REGISTRY_PATH", tmp_path / "dashboards.db")

PAGES = {
    "Command Center": "nav_pages/command_center.py",
    "Revenue Forecast": "nav_pages/revenue_forecast.py",
    "AI Copilot": "nav_pages/ai_copilot.py",
    "Player Intelligence": "nav_pages/player_intelligence.py",
    "Player Profile": "nav_pages/player_profile.py",
    "CRM Automation": "nav_pages/crm_automation.py",
    "Casino": "nav_pages/casino.py",
    "Sportsbook": "nav_pages/sportsbook.py",
    "Acquisition": "nav_pages/acquisition.py",
    "Revenue & Finance": "nav_pages/finance.py",
    "Risk & Compliance": "nav_pages/risk.py",
    "My Dashboard": "nav_pages/custom_dashboard.py",
}


# Player Profile (single-player fact cards) and Revenue Forecast (forecast cards) use custom
# HTML cards rather than st.metric and intentionally have no governed KPI row. My Dashboard is a
# self-serve chart builder with no governed KPI cards at all — every chart is user-defined.
PAGES_WITHOUT_GOVERNED_METRICS = {"Player Profile", "Revenue Forecast", "My Dashboard"}


def _widget(elements, label):
    return next(element for element in elements if element.label == label)


def _assert_governed_metrics(app, page):
    required = ["Definition:", "Formula:", "Source:", "Period:", "Status:", "Last updated:"]
    if page in PAGES_WITHOUT_GOVERNED_METRICS:
        assert not app.metric
        return
    assert app.metric
    for metric in app.metric:
        assert metric.help
        assert all(field in metric.help for field in required), metric.label


def test_all_pages_render_for_global_and_market_filters():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    governed_labels = set()

    for page in PAGES:
        _widget(app.radio, "Test page").set_value(page).run()
        assert not app.exception, f"{page}: {[error.message for error in app.exception]}"
        _assert_governed_metrics(app, page)
        governed_labels.update(metric.label for metric in app.metric)

    assert {
        "Estimated NGR",
        "Predicted Remaining LTV 90D",
        "Observed FTD Conversion D30",
        "Observed Retention D30",
        "Observed Actual RTP",
    } <= governed_labels

    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    _widget(app.selectbox, "Market").set_value("Canada").run()
    for page in PAGES:
        _widget(app.radio, "Test page").set_value(page).run()
        assert not app.exception, f"Canada / {page}: {[error.message for error in app.exception]}"
        _assert_governed_metrics(app, page)
        assert _widget(app.selectbox, "Market").value == "Canada"


def test_navigation_groups_icons_and_persistent_filter_keys_are_declared():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    _widget(app.segmented_control, "Design").set_value("Light").run()
    assert not app.exception
    assert _widget(app.segmented_control, "Design").value == "Light"
    _widget(app.selectbox, "Market").set_value("Canada").run()
    assert _widget(app.selectbox, "Market").value == "Canada"

    source = APP.read_text(encoding="utf-8")
    for group in ["Executive", "Customers", "Performance", "Operations", "Explore"]:
        assert f'"{group}"' in source
    for icon in ["dashboard", "insights", "psychology", "person_search", "badge", "campaign", "casino", "sports_soccer", "trending_up", "account_balance", "gpp_good", "dashboard_customize"]:
        assert f":material/{icon}:" in source
    assert ':material/upload_file:' in source
    assert 'title="Data Import Studio"' in source
    assert 'title="My Dashboard"' in source
    assert 'key="global_date_range"' in source
    assert 'key="global_market"' in source
    assert 'position="sidebar"' in source
    assert "render_floating_assistant(context, current_page)" in source
    assert "showSidebarNavigation = true" in CONFIG.read_text(encoding="utf-8")

    theme = THEME.read_text(encoding="utf-8")
    components = COMPONENTS.read_text(encoding="utf-8")
    assert "white-space:normal!important" in theme
    assert "text-overflow:clip!important" in theme
    assert "columns or len(items)" in components
    assert "max-width: 600px" in theme
    assert "calc(50% - .4rem)" in theme
    assert ':has([data-testid="stMetric"])' in theme


def test_command_center_has_performance_and_action_layers():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    assert not app.exception
    assert [metric.label for metric in app.metric] == [
        "Observed Total GGR", "Estimated NGR", "Observed Active Players",
        "Observed Deposits", "Observed FTD", "Observed Blended Hold",
    ]
    assert len(app.get("plotly_chart")) == 1
    html = "\n".join(str(item.value) for item in app.markdown)
    for heading in ("Performance at a glance", "Action required"):
        assert heading in html
    for heading in ("Forward outlook", "Recommended decisions"):
        assert heading not in html
    # Alerts come from the same governed Decision Engine as AI Copilot (single source of truth,
    # no duplicated/inconsistent logic) — at most the top 6 by severity, never a fabricated count.
    assert 1 <= html.count("command-alert ") <= 6


def test_revenue_forecast_has_outlook_layer_and_no_duplicated_recommendations():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    _widget(app.radio, "Test page").set_value("Revenue Forecast").run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 2
    html = "\n".join(str(item.value) for item in app.markdown)
    assert "Forward outlook" in html
    assert "Forecast by week" in html
    for heading in ("Recommended decisions", "recommendation-card", "WHAT IS HAPPENING?"):
        assert heading not in html


def test_player_intelligence_has_segments_charts_and_crm_export():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    _widget(app.radio, "Test page").set_value("Player Intelligence").run()
    assert not app.exception
    assert not app.tabs
    assert len(app.get("plotly_chart")) == 2
    segment = _widget(app.selectbox, "Business segment")
    assert segment.options == [
        "All players", "VIP active", "VIP at risk", "New FTD", "Growing players",
        "Became inactive", "Potential bonus abuse", "RG risk", "High future value",
    ]
    assert _widget(app.toggle, "CRM-safe export only").value is True
    assert len(app.get("download_button")) == 1
    initial_export_label = app.get("download_button")[0].label
    assert initial_export_label.startswith("Export ")
    segment.set_value("VIP at risk").run()
    assert not app.exception
    assert app.get("download_button")[0].label != initial_export_label


def test_player_profile_shows_identity_card_tabs_and_peer_comparison():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    _widget(app.radio, "Test page").set_value("Player Profile").run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Value & cash", "Gaming behavior", "Risk & RG", "Timeline", "CRM history"]
    html = "\n".join(str(item.value) for item in app.markdown)
    assert "player-avatar material-symbols-rounded" in html
    assert html.count("player-fact-icon material-symbols-rounded") >= 20
    assert len(app.get("plotly_chart")) >= 7  # 5 risk gauges + favorite games + peer comparison + timeline
    segment = _widget(app.selectbox, "Business segment")
    assert segment.options == [
        "All players", "VIP active", "VIP at risk", "New FTD", "Growing players",
        "Became inactive", "Potential bonus abuse", "RG risk", "High future value",
    ]
    segment.set_value("VIP at risk").run()
    assert not app.exception


def test_my_dashboard_builds_and_removes_a_custom_widget():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    app = _widget(app.radio, "Test page").set_value("My Dashboard").run()
    assert not app.exception
    html = "\n".join(str(item.value) for item in app.markdown)
    assert "This dashboard is empty" in html

    # Default "Add visualization" form: type=KPI, dataset=executive — add a GGR KPI widget.
    _widget(app.multiselect, "Measures (1 to 1)").set_value(["ggr"]).run()
    app = _widget(app.button, "Add to dashboard").set_value(True).run()
    assert not app.exception
    assert [metric.label for metric in app.metric] == ["Observed GGR"]

    widget_delete = next(button for button in app.button if button.key and button.key.startswith("del_"))
    app = widget_delete.set_value(True).run()
    assert not app.exception
    assert not app.metric
    html = "\n".join(str(item.value) for item in app.markdown)
    assert "This dashboard is empty" in html
