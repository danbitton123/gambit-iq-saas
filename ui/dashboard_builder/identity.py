from __future__ import annotations

"""Tenant/user identity for the dashboard builder.

CasinoAI has no login system today — the whole app is one operator per deployment (see
config.OPERATOR). tenant_id uses that, which is the correct scoping unit for a real multi-tenant
deployment where each casino gets its own configured instance/row. user_id is a pseudo-identity
generated once per browser session (st.session_state), NOT a real authenticated identity — it
does not identify a person across devices or sessions. Every dashboard read/write already goes
through dashboard_builder.persistence, which scopes by tenant_id (and user_id for ownership) in
the SQL WHERE clause itself; wiring in real authentication later only means replacing how these
two ids are derived, not touching the isolation logic itself.
"""

from uuid import uuid4

import streamlit as st

from config import OPERATOR

_SESSION_USER_KEY = "dashboard_builder_user_id"


def tenant_id() -> str:
    return OPERATOR


def user_id() -> str:
    if _SESSION_USER_KEY not in st.session_state:
        st.session_state[_SESSION_USER_KEY] = f"user-{uuid4().hex[:8]}"
    return st.session_state[_SESSION_USER_KEY]
