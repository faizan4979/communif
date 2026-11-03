"""
Main Streamlit Application Entrypoint for DDSS.
Coordinates page navigation, branding, user authentication state,
and delegates rendering to modular views.
"""

import os
import sys

# Streamlit Cloud runs this file with only frontend/ on sys.path; add the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import streamlit as st
from PIL import Image

from frontend.config import BACKEND_URL
from frontend.ui_components import apply_custom_theme, render_header, render_sidebar
from frontend.student_view import render_student_portal
from frontend.admin_view import render_admin_dashboard

st.set_page_config(
    page_title="DDSS - Dawood Data Science Society",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_custom_theme()
render_header()
render_sidebar()

# Session State Initialization
if "user" not in st.session_state:
    st.session_state["user"] = None
if "token" not in st.session_state:
    st.session_state["token"] = None


# Check user login status
user = st.session_state.get("user")

if not user:
    # Public Mode: Student Portal & Login Tabs
    portal_tab, login_tab = st.tabs(["Student Registration Portal", "Cabinet & Admin Login"])

    with portal_tab:
        render_student_portal()

    with login_tab:
        st.subheader("Dawood Data Science Society - Portal Sign In")
        st.caption("Authorized access for Society Admin and Cabinet Executive Members.")

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username").strip().lower()
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            login_submitted = st.form_submit_button("Sign In to Portal", use_container_width=True)

        if login_submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                try:
                    payload = {"username": username, "password": password}
                    res = requests.post(f"{BACKEND_URL}/api/auth/login", json=payload, timeout=5)
                    if res.status_code == 200:
                        login_data = res.json()
                        st.session_state["token"] = login_data.get("token")
                        st.session_state["user"] = login_data
                        st.success(f"Welcome back, {login_data.get('full_name')}!")
                        st.rerun()
                    else:
                        err_detail = res.json().get("detail", "Invalid credentials")
                        st.error(err_detail)
                except Exception as e:
                    st.error(f"Cannot connect to backend server at {BACKEND_URL}: {str(e)}")


else:
    # Logged In Mode
    user_role = user.get("role")

    if user_role == "admin":
        nav_mode = st.radio(
            "Navigation Mode:",
            ["Admin Dashboard", "Student Portal (Preview)"],
            horizontal=True
        )
        if nav_mode == "Admin Dashboard":
            render_admin_dashboard()
        else:
            render_student_portal()
    else:
        st.error("Unknown user role. Only admin access is available.")
