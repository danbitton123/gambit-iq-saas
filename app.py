from __future__ import annotations

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_TAGLINE, OPERATOR
from data.repository import SQLContext, get_repository
from ui.theme import apply_theme, brand


st.set_page_config(
    page_title=f"{APP_NAME} · Operator Intelligence",
    page_icon="♠",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


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
        ],
    },
    position="sidebar",
    expanded=True,
)

brand()

st.sidebar.markdown(f"**{OPERATOR}**")
st.sidebar.caption(APP_TAGLINE)
st.sidebar.divider()

repo = get_repository()
min_ts, max_ts = repo.date_bounds()
min_date, max_date = min_ts.date(), max_ts.date()
default_start = max(pd.Timestamp(min_date), pd.Timestamp(max_date) - pd.Timedelta(89, unit="D")).date()
date_range = st.sidebar.date_input("Global date range", value=(default_start, max_date), min_value=min_date, max_value=max_date, key="global_date_range")
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, max_date
country = st.sidebar.selectbox("Market", ["All markets"] + repo.countries(), key="global_market")

context = SQLContext(repo, pd.Timestamp(start_date), pd.Timestamp(end_date), country)
st.session_state["gambit_sql_context"] = context

st.sidebar.divider()
st.sidebar.markdown(
    f"<div class='filter-summary'><span>ACTIVE SCOPE</span><strong>{country}</strong>"
    f"<small>{start_date:%d %b %Y} – {end_date:%d %b %Y} · USD</small></div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("<div class='live-pill'><span class='live-dot'></span> All systems operational</div>", unsafe_allow_html=True)
st.sidebar.caption("Demo environment · Synthetic data only")
st.sidebar.caption("Use the ◀ control above to collapse the sidebar")

if not context.event_count():
    st.warning("No activity is available for this period and market. Choose a wider date range or another market.")
else:
    navigation.run()
