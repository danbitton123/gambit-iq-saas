import streamlit as st

from pages.forecast_recommendations import render

render(st.session_state["gambit_sql_context"])
