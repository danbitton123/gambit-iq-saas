import streamlit as st

from pages.player_intelligence import render

render(st.session_state["gambit_sql_context"])
