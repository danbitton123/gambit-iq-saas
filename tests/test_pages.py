from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"
HARNESS = Path(__file__).resolve().parent / "app_harness.py"
CONFIG = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
THEME = Path(__file__).resolve().parents[1] / "ui" / "theme.py"
COMPONENTS = Path(__file__).resolve().parents[1] / "ui" / "components.py"

PAGES = {
    "Command Center": "nav_pages/command_center.py",
    "AI Copilot": "nav_pages/ai_copilot.py",
    "Player Intelligence": "nav_pages/player_intelligence.py",
    "CRM Automation": "nav_pages/crm_automation.py",
    "Casino": "nav_pages/casino.py",
    "Sportsbook": "nav_pages/sportsbook.py",
    "Acquisition": "nav_pages/acquisition.py",
    "Revenue & Finance": "nav_pages/finance.py",
    "Risk & Compliance": "nav_pages/risk.py",
}


def _widget(elements, label):
    return next(element for element in elements if element.label == label)


def _assert_governed_metrics(app):
    required = ["Definition:", "Formula:", "Source:", "Period:", "Status:", "Last updated:"]
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
        _assert_governed_metrics(app)
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
        _assert_governed_metrics(app)
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
    for group in ["Executive", "Customers", "Performance", "Operations"]:
        assert f'"{group}"' in source
    for icon in ["dashboard", "psychology", "person_search", "campaign", "casino", "sports_soccer", "trending_up", "account_balance", "gpp_good"]:
        assert f":material/{icon}:" in source
    assert ':material/upload_file:' in source
    assert 'title="Data Import Studio"' in source
    assert 'key="global_date_range"' in source
    assert 'key="global_market"' in source
    assert 'position="sidebar"' in source
    assert "showSidebarNavigation = true" in CONFIG.read_text(encoding="utf-8")

    theme = THEME.read_text(encoding="utf-8")
    components = COMPONENTS.read_text(encoding="utf-8")
    assert "white-space:normal!important" in theme
    assert "text-overflow:clip!important" in theme
    assert "columns or len(items)" in components
    assert "max-width: 600px" in theme
    assert "calc(50% - .4rem)" in theme
    assert ':has([data-testid="stMetric"])' in theme


def test_command_center_has_complete_executive_decision_layers():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    assert not app.exception
    assert [metric.label for metric in app.metric] == [
        "Observed Total GGR", "Estimated NGR", "Observed Active Players",
        "Observed Deposits", "Observed FTD", "Observed Blended Hold",
    ]
    assert len(app.get("plotly_chart")) == 2
    html = "\n".join(str(item.value) for item in app.markdown)
    for heading in ("Performance at a glance", "Action required", "Forward outlook", "Recommended decisions"):
        assert heading in html
    assert html.count("command-alert ") == 6
    assert html.count("recommendation-card") == 4
    for question in ("WHAT IS HAPPENING?", "WHY?", "ESTIMATED IMPACT", "RECOMMENDED ACTION"):
        assert html.count(question) == 4


def test_player_360_segments_record_tabs_and_crm_export():
    app = AppTest.from_file(HARNESS, default_timeout=30).run()
    _widget(app.radio, "Test page").set_value("Player Intelligence").run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Value & cash", "Gaming behavior", "Risk & RG", "Timeline", "CRM history"]
    html = "\n".join(str(item.value) for item in app.markdown)
    assert "player-avatar material-symbols-rounded" in html
    assert html.count("player-fact-icon material-symbols-rounded") >= 20
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
