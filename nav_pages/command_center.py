import streamlit as st

from pages.overview import render

render(st.session_state["gambit_sql_context"])
