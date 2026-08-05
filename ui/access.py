from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from auth.service import AuthError, AuthUser, authenticate_email, get_user, list_imports, register_email, upsert_oidc_user
from config import DB_PATH
from data.repository import get_repository
from data.tenant import ImportValidationError, ingest_excel_workbooks, provision_demo_tenant, tenant_db_path, tenant_has_data


DEMO_USER = AuthUser("demo", "demo@gambit-iq.local", "Demo Operator", "test")


def _google_provider() -> str | None | bool:
    try:
        auth = st.secrets.get("auth")
        if not auth:
            return False
        if "google" in auth:
            return "google"
        if "accounts.google.com" in str(auth.get("server_metadata_url", "")):
            return None
    except Exception:
        pass
    return False


def _landing() -> None:
    st.markdown("""
      <section class="welcome-hero">
        <div class="welcome-badge"><span class="material-symbols-rounded">shield_lock</span> SECURE OPERATOR INTELLIGENCE</div>
        <h1>Turn gaming data into<br><em>decisions that perform.</em></h1>
        <p>One governed workspace for revenue, players, risk, acquisition and operational action.</p>
        <div class="welcome-proof"><span><b>10</b> decision rules</span><span><b>9</b> intelligence modules</span><span><b>1</b> isolated workspace</span></div>
      </section>
    """, unsafe_allow_html=True)


def require_user() -> AuthUser | None:
    if os.getenv("GAMBIT_AUTH_BYPASS") == "1":
        return DEMO_USER
    if getattr(st.user, "is_logged_in", False):
        email = str(st.user.get("email", "")).strip()
        if email:
            return upsert_oidc_user(email, str(st.user.get("name", email.split("@")[0])))
    user_id = st.session_state.get("auth_user_id")
    if user_id:
        user = get_user(user_id)
        if user:
            return user
        st.session_state.pop("auth_user_id", None)

    left, right = st.columns([1.35, 1])
    with left:
        _landing()
        st.markdown("""
          <div class="welcome-features">
            <div><span class="material-symbols-rounded">database</span><strong>Your data, isolated</strong><small>One private analytical warehouse per account.</small></div>
            <div><span class="material-symbols-rounded">rule</span><strong>Governed by design</strong><small>Definitions, sources and model status stay visible.</small></div>
            <div><span class="material-symbols-rounded">rocket_launch</span><strong>Excel to action</strong><small>Upload operational tables and refresh every dashboard.</small></div>
          </div>
        """, unsafe_allow_html=True)
    with right:
        st.markdown("<div class='auth-title'><span>WELCOME TO GAMBIT IQ</span><h2>Unlock your workspace</h2><p>Sign in or create a secure operator account.</p></div>", unsafe_allow_html=True)
        google = _google_provider()
        if st.button("Continue with Google", icon=":material/account_circle:", width="stretch", disabled=google is False, key="google_login"):
            st.login(google if isinstance(google, str) else None)
        if google is False:
            st.caption("Google login becomes active when the administrator configures Google OIDC secrets.")
        st.markdown("<div class='auth-divider'><span>or continue with email</span></div>", unsafe_allow_html=True)
        login_tab, signup_tab = st.tabs(["Sign in", "Create account"])
        with login_tab:
            with st.form("email_login", clear_on_submit=False):
                email = st.text_input("Email", placeholder="name@company.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in securely", type="primary", width="stretch")
                if submitted:
                    try:
                        user = authenticate_email(email, password)
                        st.session_state["auth_user_id"] = user.user_id
                        st.rerun()
                    except AuthError as exc:
                        st.error(str(exc))
        with signup_tab:
            with st.form("email_signup", clear_on_submit=False):
                name = st.text_input("Full name", placeholder="Your name")
                signup_email = st.text_input("Work email", placeholder="name@company.com")
                signup_password = st.text_input("Create password", type="password", help="10+ characters with uppercase, lowercase and a number.")
                accepted = st.checkbox("I accept the secure processing of my uploaded demo data.")
                created = st.form_submit_button("Create secure workspace", type="primary", width="stretch", disabled=not accepted)
                if created:
                    try:
                        user = register_email(signup_email, signup_password, name)
                        st.session_state["auth_user_id"] = user.user_id
                        st.rerun()
                    except AuthError as exc:
                        st.error(str(exc))
        st.caption("Passwords are salted and hashed. Gambit IQ never stores plaintext passwords.")
    return None


def logout(user: AuthUser) -> None:
    # The active OIDC session decides whether Streamlit must also clear its
    # identity cookie. An email account can later use Google with the same email.
    if getattr(st.user, "is_logged_in", False):
        st.logout()
    st.session_state.clear()
    st.rerun()


def _schema_table() -> pd.DataFrame:
    return pd.DataFrame([
        ("players", "Required", "Player identity, registration, market, channel, device, VIP, KYC"),
        ("games", "Required with sessions", "Game, family, theoretical RTP and provider"),
        ("sessions", "At least one activity table", "Casino bets, payouts, duration and game activity"),
        ("transactions", "At least one activity table", "Deposits, withdrawals, approvals, methods and fees"),
        ("sports_bets", "At least one activity table", "Stakes, payouts, odds, sport, live flag and event"),
    ], columns=["Excel sheet", "Requirement", "Purpose"])


def render_onboarding(user: AuthUser) -> None:
    st.markdown("""
      <section class="onboarding-hero"><span class="material-symbols-rounded">cloud_upload</span>
      <div><small>PRIVATE DATA ONBOARDING</small><h1>Build your first intelligence workspace</h1>
      <p>Upload governed Excel tables. Gambit IQ validates them before replacing your current warehouse.</p></div></section>
    """, unsafe_allow_html=True)
    step1, step2, step3 = st.columns(3)
    for column, number, icon, title, text in [
        (step1, "01", "table_view", "Prepare tables", "Use one workbook with named sheets or one workbook per table."),
        (step2, "02", "verified", "Validate safely", "Columns, identifiers and relationships are checked before activation."),
        (step3, "03", "dashboard", "Unlock dashboards", "Your isolated warehouse refreshes every available KPI."),
    ]:
        with column:
            st.markdown(f"<div class='onboarding-step'><b>{number}</b><span class='material-symbols-rounded'>{icon}</span><strong>{title}</strong><small>{text}</small></div>", unsafe_allow_html=True)
    st.dataframe(_schema_table(), width="stretch", hide_index=True)
    files = st.file_uploader("Upload Excel workbooks", type=["xlsx"], accept_multiple_files=True, max_upload_size=25,
                             help="Recognized sheets: players, games, sessions, transactions, sports_bets.")
    action, demo = st.columns([1, 1])
    with action:
        if st.button("Validate and activate my data", type="primary", width="stretch", disabled=not files):
            try:
                with st.status("Building your isolated warehouse…", expanded=True) as status:
                    path, manifest, model_status = ingest_excel_workbooks(user.user_id, files)
                    st.write(f"Validated {sum(manifest.values()):,} rows across {sum(value > 0 for value in manifest.values())} populated tables.")
                    st.write("Predictive models available." if model_status == "available" else "Predictive fields will display Missing data until sufficient history is available.")
                    get_repository.clear()
                    status.update(label="Workspace ready", state="complete")
                st.rerun()
            except ImportValidationError as exc:
                st.error(str(exc))
    with demo:
        if st.button("Explore with secure demo data", width="stretch"):
            provision_demo_tenant(user.user_id)
            get_repository.clear()
            st.rerun()
    st.caption("Imports are isolated by account. Existing data is replaced only after the new workbook passes validation.")


def render_workspace_manager(user: AuthUser) -> None:
    with st.sidebar.expander("Data workspace", icon=":material/database:"):
        source = "Demo dataset" if user.user_id == "demo" else "Private tenant warehouse"
        st.caption(source)
        files = st.file_uploader("Replace with Excel", type=["xlsx"], accept_multiple_files=True, max_upload_size=25, key="sidebar_excel")
        if st.button("Validate & replace", width="stretch", disabled=not files, key="sidebar_import"):
            try:
                _, manifest, model_status = ingest_excel_workbooks(user.user_id, files)
                get_repository.clear()
                st.success(f"{sum(manifest.values()):,} rows activated · models {model_status}")
                st.rerun()
            except ImportValidationError as exc:
                st.error(str(exc))
        if user.user_id != "demo":
            history = list_imports(user.user_id, 3)
            for item in history:
                st.caption(f"{item['status']} · {item['rows_loaded']:,} rows · {item['created_at'][:10]}")


def repository_path(user: AuthUser) -> str:
    return str(DB_PATH if user.user_id == "demo" else tenant_db_path(user.user_id))
