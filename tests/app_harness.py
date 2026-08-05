"""Streamlit test harness for rendering every dashboard module."""

import pandas as pd
import streamlit as st

from data.repository import SQLContext, get_repository
from pages import acquisition, ai_copilot, casino, crm, finance, overview, player_intelligence, risk, sportsbook


PAGES = {
    "Command Center": overview.render,
    "AI Copilot": ai_copilot.render,
    "Player Intelligence": player_intelligence.render,
    "CRM Automation": crm.render,
    "Casino": casino.render,
    "Sportsbook": sportsbook.render,
    "Acquisition": acquisition.render,
    "Revenue & Finance": finance.render,
    "Risk & Compliance": risk.render,
}

repo = get_repository()
market = st.selectbox("Market", ["All markets"] + repo.countries())
page = st.radio("Test page", list(PAGES))
context = SQLContext(repo, pd.Timestamp("2026-05-07"), pd.Timestamp("2026-08-04"), market)
PAGES[page](context)
