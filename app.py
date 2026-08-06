from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_TAGLINE, OPERATOR
from data.errors import DataConnectionError, SQLQueryError
from data.repository import SQLContext, get_repository
from ui.states import (
    render_connection_error,
    render_invalid_filter,
    render_model_unavailable,
    render_no_data,
    render_sql_error,
    render_stale_data,
    render_unexpected_error,
    validate_filters,
)
from ui.theme import apply_theme
from ui.copilot_assistant import render_floating_assistant


ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)

st.set_page_config(
    page_title=f"{APP_NAME} · Operator Intelligence",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _reference() -> str:
    return uuid4().hex[:8].upper()


def main() -> None:
    # Streamlit renders this native logo above the navigation tree, including on mobile.
    st.logo(str(ROOT / "assets/casino_ai_logo.svg"), size="large", icon_image=str(ROOT / "assets/casino_ai_icon.svg"))

    navigation = st.navigation(
        {
            "Executive": [
                st.Page("nav_pages/command_center.py", title="Command Center", icon=":material/dashboard:", url_path="command-center", default=True),
                st.Page("nav_pages/ai_copilot.py", title="AI Copilot", icon=":material/psychology:", url_path="ai-copilot"),
            ],
            "Customers": [
                st.Page("nav_pages/player_intelligence.py", title="Player Intelligence", icon=":material/person_search:", url_path="player-intelligence"),
                st.Page("nav_pages/crm_automation.py", title="CRM Automation", icon=":material/campaign:", url_path="crm-automation"),
            ],
            "Performance": [
                st.Page("nav_pages/casino.py", title="Casino", icon=":material/casino:", url_path="casino"),
                st.Page("nav_pages/sportsbook.py", title="Sportsbook", icon=":material/sports_soccer:", url_path="sportsbook"),
                st.Page("nav_pages/acquisition.py", title="Acquisition", icon=":material/trending_up:", url_path="acquisition"),
            ],
            "Operations": [
                st.Page("nav_pages/finance.py", title="Revenue & Finance", icon=":material/account_balance:", url_path="revenue-finance"),
                st.Page("nav_pages/risk.py", title="Risk & Compliance", icon=":material/gpp_good:", url_path="risk-compliance"),
                st.Page("nav_pages/data_import.py", title="Data Import Studio", icon=":material/upload_file:", url_path="data-import"),
            ],
        },
        position="sidebar",
        expanded=True,
    )

    design = st.sidebar.segmented_control(
        "Design", ["Dark", "Light"], default="Dark", key="design_mode", width="stretch"
    ) or "Dark"
    apply_theme(design)
    st.sidebar.markdown(f"**{OPERATOR}**")
    st.sidebar.caption(APP_TAGLINE)
    st.sidebar.divider()

    with st.spinner("Loading governed data…"):
        repo = get_repository()
        min_ts, max_ts = repo.date_bounds()
        countries = repo.countries()

    if pd.isna(min_ts) or pd.isna(max_ts):
        render_no_data()
        return

    min_date, max_date = min_ts.date(), max_ts.date()
    default_start = max(pd.Timestamp(min_date), pd.Timestamp(max_date) - pd.Timedelta(89, unit="D")).date()
    date_range = st.sidebar.date_input(
        "Global date range", value=(default_start, max_date), min_value=min_date,
        max_value=max_date, key="global_date_range"
    )
    country = st.sidebar.selectbox("Market", ["All markets", *countries], key="global_market")
    try:
        start_date, end_date = validate_filters(date_range, country, countries)
    except ValueError as exc:
        render_invalid_filter(str(exc))
        return

    context = SQLContext(repo, pd.Timestamp(start_date), pd.Timestamp(end_date), country)
    st.session_state["gambit_sql_context"] = context
    st.sidebar.divider()
    st.sidebar.markdown(
        f"<div class='filter-summary'><span>ACTIVE SCOPE</span><strong>{country}</strong>"
        f"<small>{start_date:%d %b %Y} – {end_date:%d %b %Y} · USD</small></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<div class='live-pill'><span class='live-dot'></span> Connected</div>", unsafe_allow_html=True)
    st.sidebar.caption("Demo environment · Synthetic data only")
    st.sidebar.caption("Use the ◀ control above to collapse the sidebar")

    latest = repo.latest_event()
    if latest is not None:
        latest_utc = latest.tz_localize("UTC") if latest.tzinfo is None else latest.tz_convert("UTC")
        if datetime.now(timezone.utc) - latest_utc.to_pydatetime() > timedelta(days=2):
            render_stale_data(f"{latest_utc:%d %b %Y, %H:%M} UTC")
    if not repo.model_available():
        render_model_unavailable()
    if not context.event_count():
        render_no_data()
        return

    with st.spinner("Preparing dashboard…"):
        current_page = getattr(navigation, "title", "Command Center")
        st.session_state["current_page"] = current_page
        navigation.run()
    render_floating_assistant(context, current_page)


try:
    main()
except DataConnectionError:
    reference = _reference()
    LOGGER.exception("Data connection failure [%s]", reference)
    render_connection_error(reference)
except SQLQueryError:
    reference = _reference()
    LOGGER.exception("SQL query failure [%s]", reference)
    render_sql_error(reference)
except Exception:  # Last-resort UI boundary: technical details remain server-side.
    reference = _reference()
    LOGGER.exception("Unhandled application failure [%s]", reference)
    render_unexpected_error(reference)
