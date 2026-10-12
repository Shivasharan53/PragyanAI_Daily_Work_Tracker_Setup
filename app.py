import os
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

st.set_page_config(
    page_title="Daily Work Tracker",
    page_icon="📘",
    layout="wide"
)

st.title("📘 Daily Work & Achievement Tracker")
st.caption("Projects • PPTs • LinkedIn • GitHub • Learning")

# ---------- CONFIGURATION ----------

def setting(key):
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")

APP_PASSWORD = setting("APP_PASSWORD")
DATABASE_URL = setting("DATABASE_URL")

if not APP_PASSWORD or not DATABASE_URL:
    st.error("Configure APP_PASSWORD and DATABASE_URL in Streamlit Secrets.")
    st.stop()

if not st.session_state.get("logged_in"):
    st.subheader("🔐 Personal Login")

    with st.form("login"):
        password = st.text_input("Enter app password", type="password")
        submit = st.form_submit_button("Login")

    if submit:
        if password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()

# Normalize common PostgreSQL URL schemes for the psycopg driver.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

# Parse the URL without ever displaying its password.
try:
    db_config = make_url(DATABASE_URL)
except Exception:
    st.error(
        "DATABASE_URL could not be parsed. In Streamlit Secrets, paste the "
        "complete Supabase Session Pooler connection string and replace only "
        "the password placeholder. Do not share the password."
    )
    st.stop()

with st.expander("🔎 Database connection diagnostics (password hidden)", expanded=True):
    st.write("Host:", db_config.host or "Not detected")
    st.write("Port:", db_config.port or "Default")
    st.write("Username:", db_config.username or "Not detected")
    st.write("Database:", db_config.database or "Not detected")
    if db_config.host and "pooler.supabase.com" in db_config.host:
        if db_config.port != 5432:
            st.warning("For Session Pooler, the port should be 5432.")
        if db_config.username and "." not in db_config.username:
            st.warning(
                "Shared Supabase Session Pooler usernames normally look like "
                "postgres.PROJECT_REF, not just postgres."
            )
    elif db_config.host and db_config.host.startswith("db.") and db_config.host.endswith(".supabase.co"):
        st.warning(
            "This looks like a direct Supabase connection. On IPv4-only hosting, "
            "use the Session Pooler connection string copied from Supabase Connect."
        )

@st.cache_resource
def get_engine(url):
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )

engine = get_engine(DATABASE_URL)

try:
