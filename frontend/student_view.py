"""
Public Student Registration Portal View for Streamlit Frontend.
Allows DUET Data Science students to view open events/forms and submit applications.
Enforces client-side validation (regex, image size & Pillow type) before calling backend.
"""

import io
from datetime import datetime
import requests
import streamlit as st
from PIL import Image

from frontend.config import BACKEND_URL


def _display_datetime(value: str, fallback: str) -> str:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(str(value).replace(" ", "T")).strftime("%d %b %Y, %I:%M %p")
    except ValueError:
        return str(value)


def render_student_portal():
    st.markdown("### Student Event & Volunteer Registration Portal")
    st.markdown(
        "Welcome to the **Dawood Data Science Society (DDSS)** official registration system. "
        "Only enrolled DUET undergraduate students with valid roll numbers may submit."
    )

    # 1. Fetch available forms from backend
    try:
        resp = requests.get(f"{BACKEND_URL}/api/public/forms", timeout=5)
        if resp.status_code == 200:
            forms = resp.json()
        else:
            st.error(f"Failed to fetch forms: {resp.text}")
            return
    except Exception as e:
        st.error(f"Cannot connect to DDSS Backend at {BACKEND_URL}. Ensure FastAPI is running.")
        return

    if not forms:
        st.info("No registration forms have been created yet. Please check back later.")
        return

    # Select Form
    form_options = {
        f"{f.get('form_id')} - {f.get('event_title')} ({f.get('form_type')} Form)": f
        for f in forms
    }
    selected_label = st.selectbox("Select an Event Registration Form:", list(form_options.keys()))
    selected_form = form_options[selected_label]

    is_open = selected_form.get("computed_is_open", False)
    status_msg = selected_form.get("status_message", "")

    # Display Form Header Card
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"#### {selected_form.get('event_title')}")
        st.markdown(f"**Form Type:** `{selected_form.get('form_type')}`")
        st.markdown(f"**Description:** {selected_form.get('description')}")
        if selected_form.get("open_time") or selected_form.get("close_time"):
            st.caption(
                f"Schedule: Opens: {_display_datetime(selected_form.get('open_time'), 'Immediately')} | "
                f"⌛ Closes: {_display_datetime(selected_form.get('close_time'), 'No deadline')}"
            )
    with col2:
        if is_open:
            st.success("OPEN FOR REGISTRATION")
        else:
            st.error(f"CLOSED\n\n_{status_msg}_")

    st.divider()

    if not is_open:
        st.warning(f"**This form is currently closed.**\n\nReason: **{status_msg}**\n\nSubmissions are disabled.")
        return

    # Registration Form Fields
    st.markdown(f"#### Submit Application for: *{selected_form.get('form_type')}*")
    with st.form("student_submission_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Candidate Full Name *", placeholder="e.g. Muhammad Ahmed")
            roll_no = st.text_input("Roll Number *", placeholder="e.g. 25F-DS-052").strip().upper()
        with c2:
            phone_no = st.text_input("Pakistani Phone Number *", placeholder="e.g. 03001234567 or +923001234567")
            dept_options = [
                "Data Science",
                "Computer Science",
                "Software Engineering",
                "Artificial Intelligence",
                "Cyber Security",
                "Telecommunication"
            ]
            department = st.selectbox("Department *", dept_options, index=0)

        university_email = st.text_input("University Email *", placeholder="e.g. 25f-ds-076@students.duet.edu.pk")

        st.markdown("##### Mandatory Student ID Card Image")
        st.markdown(
            """
            <style>
            [data-testid="stFileUploaderDropzoneInstructions"] small { font-size: 0 !important; }
            [data-testid="stFileUploaderDropzoneInstructions"] small::after { content: "80 KB per file • JPG, JPEG, PNG"; font-size: 0.875rem; }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.caption("Upload a clear photo of your DUET student ID card. Max size: **80 KB**. Accepted formats: **JPG, JPEG, PNG**.")
        uploaded_file = st.file_uploader(
            "Choose Student ID Card Image",
            type=["jpg", "jpeg", "png"],
            key="id_card_uploader"
        )

        submit_btn = st.form_submit_button("Submit Application", use_container_width=True)

    if submit_btn:
        # Frontend Validations
        if not name or not roll_no or not phone_no or not university_email or not uploaded_file:
            st.error("Please fill in all required fields and upload your ID card image.")
            return

        # Validate University Email format
        import re
        clean_univ_email = university_email.strip().lower()
        if not clean_univ_email.endswith("@students.duet.edu.pk"):
            st.error("Invalid university email. Only addresses ending in @students.duet.edu.pk are accepted.")
            return

        duet_email_pattern = re.compile(r"^\d{2}[a-z]-[a-z]{2,5}-\d{2,4}@students\.duet\.edu\.pk$", re.IGNORECASE)
        if not duet_email_pattern.fullmatch(clean_univ_email):
            st.error("Invalid university email format. Use format like 25f-ds-076@students.duet.edu.pk")
            return

        # Roll number portion of the university email must match the student's entered roll number
        email_roll_part = clean_univ_email.split("@")[0].upper()
        if email_roll_part != roll_no.strip().upper():
            st.error(f"The roll number in university email ({email_roll_part}) does not match entered roll number ({roll_no.strip().upper()}).")
            return

        # Name length and letters check
        if len(name.strip()) < 3 or len(name.strip()) > 60:
            st.error("Candidate name must be between 3 and 60 characters.")
            return

        # ID Card File Size Check in Frontend (80 KB = 81,920 bytes)
        file_bytes = uploaded_file.getvalue()
        if len(file_bytes) > 81920:
            st.error("Image must be 80 KB or smaller.")
            return

        # ID Card Real Image Validation in Frontend using Pillow
        try:
            pil_img = Image.open(io.BytesIO(file_bytes))
            pil_img.verify()
            fmt = (pil_img.format or "").upper()
            if fmt not in ["JPEG", "JPG", "PNG"]:
                st.error(f"Unsupported image format '{fmt}'. Only JPG, JPEG, or PNG allowed.")
                return
        except Exception as e:
            st.error(f"Corrupted or invalid image file: {str(e)}")
            return

        # Send to Backend API
        with st.spinner("Submitting your application to DDSS..."):
            try:
                files = {
                    "id_card_picture": (uploaded_file.name, file_bytes, uploaded_file.type)
                }
                data = {
                    "form_id": selected_form.get("form_id"),
                    "candidate_name": name.strip(),
                    "roll_no": roll_no,
                    "phone_no": phone_no.strip(),
                    "department": department,
                    "email": university_email.strip(),
                    "university_email": university_email.strip()
                }
                api_resp = requests.post(f"{BACKEND_URL}/api/public/submit", data=data, files=files, timeout=10)

                if api_resp.status_code == 200:
                    res_json = api_resp.json()
                    st.balloons()
                    st.success("Application submitted successfully!")
                    st.markdown(
                        f"""
                        <div style="background-color: #ECFDF5; color: #1E293B; border: 2px solid #10B981; border-radius: 10px; padding: 20px; margin: 16px 0;">
                            <h3 style="color: #065F46; margin-top: 0;">Registration Confirmed</h3>
                            <p><strong>Reference Number:</strong> <code style="font-size: 18px; color: #1E3A8A; background: #DBEAFE; padding: 2px 8px; border-radius: 4px;">{res_json.get('reference_number')}</code></p>
                            <p><strong>Event:</strong> {res_json.get('event_title')}</p>
                            <p><strong>Candidate Name:</strong> {res_json.get('candidate_name')}</p>
                            <p><strong>Roll Number:</strong> {res_json.get('roll_no')}</p>
                            <p><strong>Status:</strong> <span style="background: #FEF3C7; color: #92400E; padding: 2px 8px; border-radius: 12px; font-weight: 600;">Pending Review</span></p>
                            <hr style="border: none; border-top: 1px solid #D1FAE5; margin: 12px 0;">
                            <p style="font-size: 13px; color: #047857; margin-bottom: 0;">
                                Please save this reference number. Your submission has entered the processing queue in FIFO order for cabinet review.
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    detail = api_resp.json().get("detail", api_resp.text)
                    st.error(f"Submission rejected: {detail}")
            except Exception as e:
                st.error(f"Error communicating with backend: {str(e)}")

    # Developer Credits
    st.divider()
    st.markdown(
        "Made by @ Hassan Ikram [25F-DS-052], Muhammad Faizan Ali [25F-DS-076], "
        "Faizan Ahmed [25F-DS-085], Muhammad Mudabbir Baig [25F-DS-087], "
        "Alishan Khan [25F-DS-093]",
        help="Project Development Team"
    )
