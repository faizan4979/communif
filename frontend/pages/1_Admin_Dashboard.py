"""
Standalone Admin Dashboard Page for Streamlit.
"""

import streamlit as st
from frontend.ui_components import apply_custom_theme, render_header, render_sidebar
from frontend.admin_view import render_admin_dashboard

st.set_page_config(
    page_title="DDSS - Admin Dashboard",
    layout="wide"
)

apply_custom_theme()
render_header()
render_sidebar()

user = st.session_state.get("user")
if not user:
    st.warning("Access Restricted. Please log in from the main portal with Admin credentials.")
elif user.get("role") != "admin":
    st.error("Access Denied: This dashboard is reserved for System Administrators only.")
else:
    render_admin_dashboard()
