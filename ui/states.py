from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st


def validate_filters(date_range, country: str, countries: list[str]) -> tuple[date, date]:
    if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:
        raise ValueError("Select both a start date and an end date.")
    start, end = date_range
    if start > end:
        raise ValueError("The start date must be before the end date.")
    if country not in ["All markets", *countries]:
        raise ValueError("The selected market is not available.")
    return start, end


def state_card(title: str, message: str, kind: str = "warning", detail: str | None = None) -> None:
    icon = {"error": "!", "warning": "!", "info": "i", "success": "✓"}.get(kind, "i")
    detail_html = f"<small>{escape(detail)}</small>" if detail else ""
    st.markdown(
        f"<section class='app-state app-state-{kind}' role='status'>"
        f"<div class='app-state-icon'>{icon}</div><div><strong>{escape(title)}</strong>"
        f"<p>{escape(message)}</p>{detail_html}</div></section>",
        unsafe_allow_html=True,
    )


def render_no_data() -> None:
    state_card("No data for this scope", "Try a wider period or another market.", "info")


def render_sql_error(reference: str) -> None:
    state_card("Data query unavailable", "We could not complete this query. Please retry shortly.", "error", f"Reference: {reference}")


def render_connection_error(reference: str) -> None:
    state_card("Connection interrupted", "The data service cannot be reached. Reconnect and retry.", "error", f"Reference: {reference}")


def render_invalid_filter(message: str) -> None:
    state_card("Invalid filter", message, "warning")


def render_model_unavailable() -> None:
    state_card("Model temporarily unavailable", "Predicted insights cannot be calculated. Observed data remains available.", "warning")


def render_stale_data(latest: str) -> None:
    state_card("Data refresh overdue", "Results may not reflect the latest activity.", "warning", f"Latest event: {latest}")


def render_unexpected_error(reference: str) -> None:
    state_card("Something went wrong", "The page was safely stopped. No technical details were exposed.", "error", f"Reference: {reference}")
