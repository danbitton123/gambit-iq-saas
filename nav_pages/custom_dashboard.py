import streamlit as st

from pages.custom_dashboard import render

render(st.session_state["gambit_sql_context"])
