import streamlit as st

from pages.data_import import render

render(st.session_state["gambit_sql_context"])
