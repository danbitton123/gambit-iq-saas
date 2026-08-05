from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"

PAGES = [
    "Command Center",
    "Player Intelligence",
    "Casino Games",
    "Sportsbook & Trading",
    "Acquisition",
    "CRM Automation",
    "Revenue & Finance",
    "Risk & Compliance",
    "AI Copilot",
]


def _widget(elements, label):
    return next(element for element in elements if element.label == label)


def _assert_governed_metrics(app):
    required = ["Definition:", "Formula:", "Source:", "Period:", "Status:", "Last updated:"]
    assert app.metric
    for metric in app.metric:
        assert metric.help
        assert all(field in metric.help for field in required), metric.label


def test_all_pages_render_for_global_and_market_filters():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception

    governed_labels = set()

    for page in PAGES:
        _widget(app.radio, "Navigation").set_value(page).run()
        assert not app.exception, f"{page}: {[error.message for error in app.exception]}"
        _assert_governed_metrics(app)
        governed_labels.update(metric.label for metric in app.metric)

    assert {
        "Estimated NGR",
        "Predicted LTV Proxy 90D",
        "Observed FTD Conversion D30",
        "Observed Retention D30",
        "Observed Actual RTP",
    } <= governed_labels

    app = AppTest.from_file(APP, default_timeout=30).run()
    _widget(app.selectbox, "Market").set_value("Canada").run()
    for page in PAGES:
        _widget(app.radio, "Navigation").set_value(page).run()
        assert not app.exception, f"Canada / {page}: {[error.message for error in app.exception]}"
        _assert_governed_metrics(app)
