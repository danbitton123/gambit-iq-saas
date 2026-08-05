import streamlit as st

from pages.crm import render

render(st.session_state["gambit_sql_context"])
