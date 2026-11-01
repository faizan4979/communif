"""Frontend configuration shared by all Streamlit views."""

import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


LOCAL_BACKEND_URL = "http://127.0.0.1:8000"


def get_backend_url() -> str:
    """Return the configured backend URL, preferring Streamlit secrets."""
    try:
        secret_url = st.secrets.get("BACKEND_URL")
    except StreamlitSecretNotFoundError:
        secret_url = None

    return str(
        secret_url or os.getenv("BACKEND_URL") or LOCAL_BACKEND_URL
    ).rstrip("/")


BACKEND_URL = get_backend_url()
