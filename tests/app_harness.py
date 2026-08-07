"""Streamlit test harness for rendering every dashboard module."""

import os

import pandas as pd
import streamlit as st

from data.repository import SQLContext, get_repository
from pages import (
    acquisition, ai_copilot, casino, crm, custom_dashboard, finance, overview,
    player_intelligence, player_profile, revenue_forecast, risk, sportsbook,
)


PAGES = {
    "Command Center": overview.render,
    "Revenue Forecast": revenue_forecast.render,
    "AI Copilot": ai_copilot.render,
    "Player Intelligence": player_intelligence.render,
    "Player Profile": player_profile.render,
    "CRM Automation": crm.render,
    "Casino": casino.render,
    "Sportsbook": sportsbook.render,
    "Acquisition": acquisition.render,
    "Revenue & Finance": finance.render,
    "Risk & Compliance": risk.render,
    "My Dashboard": custom_dashboard.render,
}

repo = get_repository(os.getenv("GAMBIT_TEST_DB") or None)
market = st.selectbox("Market", ["All markets"] + repo.countries())
page = st.radio("Test page", list(PAGES))
context = SQLContext(repo, pd.Timestamp("2026-05-07"), pd.Timestamp("2026-08-04"), market)
PAGES[page](context)
