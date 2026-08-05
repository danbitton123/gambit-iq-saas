import streamlit as st

from pages.finance import render

render(st.session_state["gambit_sql_context"])
