import streamlit as st

from pages.revenue_forecast import render

render(st.session_state["gambit_sql_context"])
