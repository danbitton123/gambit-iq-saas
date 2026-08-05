from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from data.repository import SQLQueryError, get_repository
from ui.states import validate_filters


ROOT = Path(__file__).resolve().parents[1]


def test_filter_validation_rejects_incomplete_reversed_and_unknown_scope():
    markets = ["Canada", "Germany"]
    assert validate_filters((date(2025, 1, 1), date(2025, 1, 2)), "Canada", markets)
    with pytest.raises(ValueError, match="both"):
        validate_filters((date(2025, 1, 1),), "Canada", markets)
    with pytest.raises(ValueError, match="before"):
        validate_filters((date(2025, 1, 2), date(2025, 1, 1)), "Canada", markets)
    with pytest.raises(ValueError, match="market"):
        validate_filters((date(2025, 1, 1), date(2025, 1, 2)), "Atlantis", markets)


def test_sql_errors_are_translated_to_a_safe_domain_error():
    with pytest.raises(SQLQueryError):
        get_repository().query("SELECT * FROM table_that_does_not_exist")


def test_app_declares_all_premium_states_logo_order_and_theme_switcher():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    states = (ROOT / "ui" / "states.py").read_text(encoding="utf-8")
    assert source.index("st.logo") < source.index("st.navigation")
    assert '"Dark", "Light"' in source
    assert "except DataConnectionError" in source
    assert "except SQLQueryError" in source
    assert "except Exception" in source
    for label in (
        "No data for this scope", "Data query unavailable", "Invalid filter",
        "Model temporarily unavailable", "Data refresh overdue", "Connection interrupted",
    ):
        assert label in states
