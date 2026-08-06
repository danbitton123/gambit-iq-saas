import streamlit as st

from pages.player_profile import render

render(st.session_state["gambit_sql_context"])
