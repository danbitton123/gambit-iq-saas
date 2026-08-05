import streamlit as st

from pages.acquisition import render

render(st.session_state["gambit_sql_context"])
