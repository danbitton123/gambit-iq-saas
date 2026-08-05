import streamlit as st

from pages.ai_copilot import render

render(st.session_state["gambit_sql_context"])
