import streamlit as st

from pages.risk import render

render(st.session_state["gambit_sql_context"])
