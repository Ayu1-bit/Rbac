"""
Authentication & role-based access control for Jewellery ERP.
"""
import bcrypt
import streamlit as st
from utils.db import run_query

# Central role list — used by app.py for nav filtering and by Settings for the "add user" form.
ROLES = ["admin", "manager", "sales", "production", "accountant", "purchasing"]

ROLE_LABELS = {
    "admin": "Administrator",
    "manager": "Manager",
    "sales": "Sales / POS",
    "production": "Production (Karigar)",
    "accountant": "Accountant",
    "purchasing": "Purchasing",
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def login(username: str, password: str) -> bool:
    user = run_query(
        "SELECT * FROM users WHERE username=? AND active=1", (username,), fetchone=True
    )
    if not user or not verify_password(password, user["password_hash"]):
        return False
    st.session_state["user"] = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"] or user["username"],
    }
    run_query("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id=?", (user["id"],))
    return True


def logout():
    st.session_state.pop("user", None)


def current_user():
    return st.session_state.get("user")


def require_role(*allowed_roles):
    """
    Call at the very top of any page (after imports, before rendering anything else).
    Stops the page from rendering further if the user isn't logged in, or isn't logged in
    with one of the allowed roles. 'admin' always passes, regardless of the roles listed.
    Call with no arguments to only require "logged in", any role.
    """
    user = current_user()
    if not user:
        st.warning("🔒 Please log in to continue.")
        st.stop()
    if allowed_roles and user["role"] not in allowed_roles and user["role"] != "admin":
        st.error("🚫 You don't have permission to view this page.")
        st.caption(f"Your role: **{ROLE_LABELS.get(user['role'], user['role'])}**")
        st.stop()


def render_sidebar_user_box():
    """Small user info + logout button, call once near the top of the sidebar."""
    user = current_user()
    if not user:
        return
    with st.sidebar:
        st.markdown(f"**👤 {user['full_name']}**")
        st.caption(f"Role: {ROLE_LABELS.get(user['role'], user['role'])}")
        if st.button("🚪 Log out", use_container_width=True):
            logout()
            st.rerun()
        st.divider()
