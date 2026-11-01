"""
UI Components and Theme Styling for DDSS Frontend.
Renders branding, dual logos (DUET left, DDSS right, title in middle),
sidebar layout, and responsive CSS styling.
"""

import os
import base64
from typing import Optional
import streamlit as st

from frontend.config import BACKEND_URL

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
DUET_LOGO_PATH = os.path.join(ASSETS_DIR, "duet_logo.png")
DDSS_LOGO_PATH = os.path.join(ASSETS_DIR, "ddss_logo.png")


def _get_base64_image(path: str) -> str:
    """Encodes local image to base64 for reliable HTML embedding."""
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
            return f"data:image/png;base64,{base64.b64encode(data).decode('utf-8')}"
    return ""


def _is_dark_theme() -> bool:
    """Detects whether Streamlit is currently rendering its dark theme."""
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def apply_custom_theme():
    """Applies clean DUET Navy & White CSS styling (light and dark aware)."""
    if _is_dark_theme():
        palette = dict(
            app_bg="#0E1117", app_fg="#E2E8F0", card_bg="#1A202C", card_border="#2D3748",
            metric_label="#94A3B8", metric_value="#F1F5F9", badge_bg="#1E3A8A",
            badge_fg="#BFDBFE", badge_border="#2563EB", divider="#2D3748",
        )
    else:
        palette = dict(
            app_bg="#F8FAFC", app_fg="#1E293B", card_bg="#FFFFFF", card_border="#E2E8F0",
            metric_label="#64748B", metric_value="#0F172A", badge_bg="#EFF6FF",
            badge_fg="#1D4ED8", badge_border="#BFDBFE", divider="#E2E8F0",
        )
    st.markdown(
        """
        <style>
        /* Main background and font */
        .stApp {
            background-color: __app_bg__;
            color: __app_fg__;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        }

        /* Top header container */
        .ddss-header-card {
            background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%);
            border-radius: 12px;
            padding: 18px 24px;
            margin-bottom: 22px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
            color: #FFFFFF;
        }
        .ddss-header-logo {
            width: 82px;
            height: 82px;
            object-fit: contain;
            border-radius: 8px;
            background: #FFFFFF;
            padding: 4px;
        }
        .ddss-header-title-box {
            text-align: center;
            flex-grow: 1;
            padding: 0 20px;
        }
        .ddss-main-title {
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin: 0;
            color: #FFFFFF;
        }
        .ddss-dept-subtitle {
            font-size: 14px;
            color: #93C5FD;
            margin: 4px 0 2px 0;
            font-weight: 500;
        }
        .ddss-tagline {
            font-size: 13px;
            color: #E2E8F0;
            font-style: italic;
            margin: 0;
            letter-spacing: 1px;
        }

        /* Metric badge styling */
        .metric-card {
            background-color: __card_bg__;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border-left: 5px solid #2563EB;
            margin-bottom: 12px;
        }
        .metric-label {
            font-size: 13px;
            color: __metric_label__;
            font-weight: 600;
            text-transform: uppercase;
        }
        .metric-value {
            font-size: 26px;
            font-weight: 700;
            color: __metric_value__;
            margin-top: 4px;
        }

        /* Form section styling */
        .form-container {
            background-color: __card_bg__;
            border-radius: 12px;
            padding: 24px;
            border: 1px solid __card_border__;
            box-shadow: 0 2px 10px rgba(0,0,0,0.04);
            margin-bottom: 20px;
        }

        /* Algorithm info callout */
        .algo-badge {
            display: inline-block;
            background-color: __badge_bg__;
            color: __badge_fg__;
            border: 1px solid __badge_border__;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 12px;
        }

        /* Sidebar dual logos */
        .sidebar-logos-container {
            display: flex;
            align-items: center;
            justify-content: space-around;
            padding: 10px 0 16px 0;
            border-bottom: 1px solid __divider__;
            margin-bottom: 16px;
        }
        .sidebar-logo {
            width: 58px;
            height: 58px;
            object-fit: contain;
            background: #FFFFFF;
            padding: 3px;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        </style>
        """.replace("__app_bg__", palette["app_bg"])
        .replace("__app_fg__", palette["app_fg"])
        .replace("__card_bg__", palette["card_bg"])
        .replace("__card_border__", palette["card_border"])
        .replace("__metric_label__", palette["metric_label"])
        .replace("__metric_value__", palette["metric_value"])
        .replace("__badge_bg__", palette["badge_bg"])
        .replace("__badge_fg__", palette["badge_fg"])
        .replace("__badge_border__", palette["badge_border"])
        .replace("__divider__", palette["divider"]),
        unsafe_allow_html=True
    )


def render_header():
    """
    Shows DUET logo on left, DDSS logo on right,
    with the title and tagline in the middle.
    """
    duet_b64 = _get_base64_image(DUET_LOGO_PATH)
    ddss_b64 = _get_base64_image(DDSS_LOGO_PATH)

    st.markdown(
        f"""
        <div class="ddss-header-card">
            <img src="{duet_b64}" class="ddss-header-logo" alt="DUET Official Logo" />
            <div class="ddss-header-title-box">
                <div class="ddss-main-title">DDSS - Dawood Data Science Society</div>
                <div class="ddss-dept-subtitle">Department of Data Science • Dawood University of Engineering and Technology</div>
                <div class="ddss-tagline">"Inspire - Analyze - Innovate"</div>
            </div>
            <img src="{ddss_b64}" class="ddss-header-logo" alt="DDSS Logo" />
        </div>
        """,
        unsafe_allow_html=True
    )


def render_sidebar():
    """
    Renders sidebar containing dual logos, branding, user session status,
    and quick actions.
    """
    duet_b64 = _get_base64_image(DUET_LOGO_PATH)
    ddss_b64 = _get_base64_image(DDSS_LOGO_PATH)

    dark = _is_dark_theme()
    title_fg = "#93C5FD" if dark else "#1E3A8A"
    muted = "#94A3B8" if dark else "#64748B"
    tagline_fg = "#CBD5E1" if dark else "#475569"
    panel_bg = "#1A202C" if dark else "#F1F5F9"
    panel_border = "#2D3748" if dark else "#CBD5E1"
    name_fg = "#F1F5F9" if dark else "#0F172A"
    info_bg = "#1E3A8A" if dark else "#EFF6FF"
    info_fg = "#BFDBFE" if dark else "#1E40AF"
    divider = "#2D3748" if dark else "#E2E8F0"

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-logos-container">
                <img src="{duet_b64}" class="sidebar-logo" alt="DUET" title="DUET" />
                <div style="font-weight: 700; font-size: 16px; color: {title_fg}; text-align: center;">
                    DDSS<br><span style="font-size: 11px; color: {muted};">DUET</span>
                </div>
                <img src="{ddss_b64}" class="sidebar-logo" alt="DDSS" title="DDSS" />
            </div>
            <div style="text-align: center; margin-bottom: 16px;">
                <span style="font-size: 11px; color: {tagline_fg}; font-style: italic;">
                    "Inspire - Analyze - Innovate"
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        user = st.session_state.get("user")
        if user:
            role_label = "Administrator" if user.get("role") == "admin" else f"Cabinet: {user.get('title', 'Member')}"
            st.markdown(
                f"""
                <div style="background-color: {panel_bg}; border-radius: 8px; padding: 12px; margin-bottom: 16px; border: 1px solid {panel_border};">
                    <div style="font-size: 11px; color: {muted}; font-weight: 600;">LOGGED IN AS</div>
                    <div style="font-size: 14px; font-weight: 700; color: {name_fg};">{user.get('full_name')}</div>
                    <div style="font-size: 12px; color: #2563EB; font-weight: 600;">{role_label}</div>
                    <div style="font-size: 11px; color: {muted};">@{user.get('username')}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Log Out", use_container_width=True, key="sidebar_logout_btn"):
                # Call backend logout
                try:
                    import requests
                    token = st.session_state.get("token")
                    if token:
                        requests.post(f"{BACKEND_URL}/api/auth/logout", headers={"X-Auth-Token": token}, timeout=3)
                except Exception:
                    pass
                st.session_state.clear()
                st.rerun()
        else:
            st.markdown(
                f"""
                <div style="background-color: {info_bg}; border-radius: 8px; padding: 10px; margin-bottom: 16px; font-size: 12px; color: {info_fg}; text-align: center;">
                    Public Portal Mode<br>
                    <span style="color: {muted};">Students can browse and submit open forms.</span>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown(
            f"""
            <div style="font-size: 11px; color: #94A3B8; text-align: center; margin-top: 20px; border-top: 1px solid {divider}; padding-top: 10px;">
                Made by @ Hassan Ikram [25F-DS-052], Muhammad Faizan Ali [25F-DS-076], Faizan Ahmed [25F-DS-085], Muhammad Mudabbir Baig [25F-DS-087], Alishan Khan [25F-DS-093]
            </div>
            """,
            unsafe_allow_html=True
        )
