import streamlit as st

from pages.casino import render

render(st.session_state["gambit_sql_context"])
