from __future__ import annotations

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_TAGLINE, OPERATOR
from data.repository import SQLContext, get_repository
from pages import acquisition, ai_copilot, casino, crm, finance, overview, player_intelligence, risk, sportsbook
from ui.theme import apply_theme, brand


st.set_page_config(
    page_title=f"{APP_NAME} · Operator Intelligence",
    page_icon="♠",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()
brand()

PAGES = {
    "Command Center": overview.render,
    "Player Intelligence": player_intelligence.render,
    "Casino Games": casino.render,
    "Sportsbook & Trading": sportsbook.render,
    "Acquisition": acquisition.render,
    "CRM Automation": crm.render,
    "Revenue & Finance": finance.render,
    "Risk & Compliance": risk.render,
    "AI Copilot": ai_copilot.render,
}

st.sidebar.markdown(f"**{OPERATOR}**")
st.sidebar.caption(APP_TAGLINE)
page = st.sidebar.radio("Navigation", list(PAGES), label_visibility="collapsed")
st.sidebar.divider()

repo = get_repository()
min_ts, max_ts = repo.date_bounds()
min_date, max_date = min_ts.date(), max_ts.date()
default_start = max(pd.Timestamp(min_date), pd.Timestamp(max_date) - pd.Timedelta(89, unit="D")).date()
date_range = st.sidebar.date_input("Global date range", value=(default_start, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, max_date
country = st.sidebar.selectbox("Market", ["All markets"] + repo.countries())
st.sidebar.caption("Operator scope")
st.sidebar.markdown(f"**{OPERATOR} · USD**")

context = SQLContext(repo, pd.Timestamp(start_date), pd.Timestamp(end_date), country)

st.sidebar.divider()
st.sidebar.markdown("<div class='live-pill'><span class='live-dot'></span> All systems operational</div>", unsafe_allow_html=True)
st.sidebar.caption("Demo environment · Synthetic data only")

player_count = context.scalar(
    "SELECT COUNT(*) FROM players WHERE (:country='All markets' OR country=:country)"
)
if not player_count:
    st.warning("No data is available for the selected filters.")
else:
    PAGES[page](context)
