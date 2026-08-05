from __future__ import annotations

import pandas as pd
from streamlit.testing.v1 import AppTest
from pathlib import Path

from config import DB_PATH
from data.decision_engine import DecisionEngine, RULE_CATALOG
from data.repository import SQLContext, SQLRepository


EXPECTED_RULES = {
    "GGR_DROP", "RTP_ANOMALY", "CAMPAIGN_LOSS", "SUPPLIER_DROP", "WITHDRAWAL_SPIKE",
    "CONVERSION_DROP", "SPORTS_EXPOSURE", "REVENUE_CONCENTRATION", "FRAUD_SIGNAL", "RG_SIGNAL",
}


def _context() -> SQLContext:
    return SQLContext(SQLRepository(DB_PATH), pd.Timestamp("2026-05-07"), pd.Timestamp("2026-08-04"), "All markets")


def test_rule_catalog_covers_every_governed_detection_and_alert_contract():
    assert set(RULE_CATALOG) == EXPECTED_RULES
    alerts = DecisionEngine(_context()).evaluate()
    assert alerts
    assert {alert.severity for alert in alerts} <= {"Critical", "High", "Medium"}
    for alert in alerts:
        assert alert.rule_id in EXPECTED_RULES
        assert alert.kpi and alert.current_value and alert.usual_value
        assert alert.impact_note and alert.probable_cause and alert.recommendation
        assert alert.team and alert.effort and alert.priority and alert.detected_at
        assert alert.financial_impact >= 0 and alert.revenue_potential >= 0
        assert 0 <= alert.confidence <= 1


def test_decision_engine_page_exposes_operational_workflow():
    app = AppTest.from_file(Path(__file__).parent / "app_harness.py", default_timeout=30).run()
    next(widget for widget in app.radio if widget.label == "Test page").set_value("AI Copilot").run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Intelligent alerts", "Recommendation center", "Rule governance"]
    assert [metric.label for metric in app.metric] == [
        "Observed Active Alerts", "Observed Critical Alerts", "Estimated Alert Impact",
        "Estimated Recovery Potential", "Observed Reviewed Decisions",
    ]
    assert {widget.label for widget in app.multiselect} == {"Severity", "Status", "Responsible team"}
    assert next(widget for widget in app.segmented_control if widget.label == "Alert status").value == "New"
    assert next(widget for widget in app.text_input if widget.label == "Result after action")
