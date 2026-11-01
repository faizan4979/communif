"""
Cabinet Member Dashboard View for Streamlit Frontend.
Provides personalized dashboard, FIFO Queue submission reviews,
DSA search and sorting, attendance marking, task assignments, and report exports.
"""

import io
import requests
import pandas as pd
import streamlit as st

from frontend.config import BACKEND_URL


def _get_headers(token: str) -> dict:
    return {"X-Auth-Token": token}


def render_cabinet_dashboard():
    user = st.session_state.get("user", {})
    token = st.session_state.get("token", "")
    headers = _get_headers(token)

    # Member Welcome Banner
    st.markdown(
        f"""
        <div style="background-color: #EFF6FF; color: #1E293B; border: 1px solid #BFDBFE; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="color: #1E3A8A; margin: 0;">Welcome, {user.get('full_name')}</h2>
                    <div style="color: #2563EB; font-weight: 600; font-size: 15px; margin-top: 2px;">
                        Portfolio: {user.get('title', 'Cabinet Member')} | @{user.get('username')}
                    </div>
                </div>
                <div style="text-align: right; font-size: 13px; color: #64748B;">
                    Society Cabinet Session: 2026<br>Dawood University of Engineering and Technology
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Overview Metrics
    try:
        stats_resp = requests.get(f"{BACKEND_URL}/api/dashboard/stats", headers=headers, timeout=5)
        if stats_resp.status_code == 200:
            stats = stats_resp.json()
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Pending Queue", stats.get("queue_size", 0))
            c2.metric("Approved", stats.get("registrations_approved", 0))
            c3.metric("Total Events", stats.get("total_events", 0))
            c4.metric("Open Forms", stats.get("forms_open", 0))
            c5.metric("Attendance", stats.get("attendance_marked", 0))
    except Exception:
        pass

    # Tabs for Cabinet Functions
    tab_queue, tab_registrations, tab_attendance, tab_assignments, tab_reports = st.tabs([
        "FIFO Queue Processor",
        "Registrations (DSA Search & Sort)",
        "Mark Attendance",
        "Volunteer Tasks",
        "Event Reports"
    ])

    # =========================================================================
    # TAB 1: FIFO Queue Processor
    # =========================================================================
    with tab_queue:
        st.subheader("Form Submissions Processing Queue (FIFO)")
        st.caption("Submissions wait in a handcrafted First-In, First-Out Queue. Process applications in exact arrival order.")

        try:
            q_resp = requests.get(f"{BACKEND_URL}/api/queue", headers=headers, timeout=5)
            if q_resp.status_code == 200:
                q_data = q_resp.json()
                q_size = q_data.get("size", 0)
                q_items = q_data.get("items", [])

                col_stat1, col_stat2 = st.columns([1, 3])
                col_stat1.metric("Items in Queue", q_size)

                if q_size > 0:
                    next_item = q_items[0]
                    with st.expander(f"Next in Queue: {next_item.get('candidate_name')} ({next_item.get('roll_no')})", expanded=True):
                        kc1, kc2 = st.columns(2)
                        with kc1:
                            st.write(f"**Reference ID:** `{next_item.get('submission_id')}`")
                            st.write(f"**Event:** {next_item.get('event_title')}")
                            st.write(f"**Candidate:** {next_item.get('candidate_name')}")
                            st.write(f"**Roll Number:** `{next_item.get('roll_no')}`")
                            st.write(f"**Department:** {next_item.get('department')}")
                            st.write(f"**Phone:** {next_item.get('phone_no')}")
                            st.write(f"**Submitted At:** {next_item.get('submitted_at')}")

                        with kc2:
                            st.write("**Student ID Card Image:**")
                            pic_file = next_item.get("id_card_file", "")
                            if pic_file:
                                img_url = f"{BACKEND_URL}/api/uploads/{pic_file}"
                                try:
                                    img_resp = requests.get(img_url, headers=headers, timeout=5)
                                    if img_resp.status_code == 200:
                                        st.image(img_resp.content, caption=f"ID Card: {next_item.get('roll_no')}", width=260)
                                    else:
                                        st.warning("ID card image unavailable.")
                                except Exception:
                                    st.warning("Could not load ID card image.")

                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("Approve Submission (Dequeue)", key="q_appr_btn", use_container_width=True):
                                p_resp = requests.post(
                                    f"{BACKEND_URL}/api/queue/process",
                                    data={"decision": "Approved"},
                                    headers=headers,
                                    timeout=5
                                )
                                if p_resp.status_code == 200:
                                    st.success(f"Approved {next_item.get('submission_id')}!")
                                    st.rerun()
                                else:
                                    st.error(f"Error: {p_resp.text}")
                        with b2:
                            if st.button("Reject Submission (Dequeue)", key="q_rej_btn", use_container_width=True):
                                p_resp = requests.post(
                                    f"{BACKEND_URL}/api/queue/process",
                                    data={"decision": "Rejected"},
                                    headers=headers,
                                    timeout=5
                                )
                                if p_resp.status_code == 200:
                                    st.warning(f"Rejected {next_item.get('submission_id')}.")
                                    st.rerun()
                                else:
                                    st.error(f"Error: {p_resp.text}")

                    # Table of remaining queue items
                    if len(q_items) > 1:
                        st.markdown("##### Upcoming in Queue:")
                        df_q = pd.DataFrame(q_items[1:])
                        cols = ["submission_id", "candidate_name", "roll_no", "event_title", "submitted_at"]
                        disp_cols = [c for c in cols if c in df_q.columns]
                        st.dataframe(df_q[disp_cols], use_container_width=True)
                else:
                    st.info("All submissions have been processed! The FIFO queue is currently empty.")
        except Exception as e:
            st.error(f"Error loading queue: {str(e)}")

    # =========================================================================
    # TAB 2: Registrations (DSA Search & Sort)
    # =========================================================================
    with tab_registrations:
        st.subheader("Registration Records with DSA Algorithms")
        st.caption("Perform live searching (Linear / Binary) and sorting (Bubble / Insertion / Merge / Quick) powered by custom DSA algorithms.")

        dataset_type = st.radio("Choose Submissions Group:", ["Volunteers", "Attendees", "All Registrations"], horizontal=True)
        ds_param = "volunteers" if dataset_type == "Volunteers" else ("attendees" if dataset_type == "Attendees" else "registrations")

        # DSA Search Controls
        st.markdown("##### Algorithm-Powered Search")
        s_col1, s_col2, s_col3, s_col4 = st.columns([2, 2, 2, 1])
        with s_col1:
            search_key = st.selectbox("Search Field:", ["candidate_name", "roll_no", "department", "event_title", "status"], key="cab_search_key")
        with s_col2:
            search_query = st.text_input("Query:", placeholder="e.g. Ahmed or 25F-DS-001", key="cab_search_q")
        with s_col3:
            algo_choice = st.selectbox("Algorithm:", ["Linear Search (O(n))", "Binary Search (O(log n))"], key="cab_search_algo")
        with s_col4:
            do_search = st.button("Search", key="cab_search_btn")

        # DSA Sort Controls
        st.markdown("##### Algorithm-Powered Sort")
        sort_col1, sort_col2, sort_col3, sort_col4 = st.columns([2, 2, 2, 1])
        with sort_col1:
            sort_key = st.selectbox("Sort Key:", ["candidate_name", "roll_no", "submitted_at", "submission_id", "status"], key="cab_sort_key")
        with sort_col2:
            sort_algo_choice = st.selectbox("Sort Algorithm:", ["Merge Sort (O(n log n))", "Quick Sort (O(n log n))", "Bubble Sort (O(n^2))", "Insertion Sort (O(n^2))"], key="cab_sort_algo")
        with sort_col3:
            sort_direction = st.selectbox("Order:", ["Ascending", "Descending"], key="cab_sort_order")
        with sort_col4:
            do_sort = st.button("Sort", key="cab_sort_btn")

        # Results Display
        display_data = None
        algo_info_box = None

        if do_search and search_query:
            algo_param = "binary" if "Binary" in algo_choice else "linear"
            search_body = {
                "dataset": ds_param,
                "key": search_key,
                "query": search_query,
                "algorithm": algo_param,
                "partial": True
            }
            try:
                s_res = requests.post(f"{BACKEND_URL}/api/dsa/search", json=search_body, headers=headers, timeout=5)
                if s_res.status_code == 200:
                    s_json = s_res.json()
                    algo_info_box = f"**{s_json.get('algorithm')}** ({s_json.get('time_complexity')}) executed: **{s_json.get('comparisons')} comparisons** across {s_json.get('total_items')} items. Found **{s_json.get('count')} matches**."
                    display_data = s_json.get("results", [])
                else:
                    st.error(s_res.text)
            except Exception as e:
                st.error(f"Search failed: {e}")

        elif do_sort:
            algo_param = "merge"
            if "Quick" in sort_algo_choice:
                algo_param = "quick"
            elif "Bubble" in sort_algo_choice:
                algo_param = "bubble"
            elif "Insertion" in sort_algo_choice:
                algo_param = "insertion"

            sort_body = {
                "dataset": ds_param,
                "key": sort_key,
                "algorithm": algo_param,
                "reverse": (sort_direction == "Descending")
            }
            try:
                st_res = requests.post(f"{BACKEND_URL}/api/dsa/sort", json=sort_body, headers=headers, timeout=5)
                if st_res.status_code == 200:
                    st_json = st_res.json()
                    algo_info_box = f"**{st_json.get('algorithm')}** ({st_json.get('time_complexity')}) completed in **{st_json.get('time_taken_seconds')} seconds** for {st_json.get('total_items')} records."
                    display_data = st_json.get("results", [])
                else:
                    st.error(st_res.text)
            except Exception as e:
                st.error(f"Sort failed: {e}")

        else:
            # Default fetch
            endpoint = "/api/submissions/volunteers" if ds_param == "volunteers" else ("/api/submissions/attendees" if ds_param == "attendees" else "/api/submissions/registrations")
            try:
                r_res = requests.get(f"{BACKEND_URL}{endpoint}", headers=headers, timeout=5)
                if r_res.status_code == 200:
                    display_data = r_res.json()
            except Exception as e:
                st.error(f"Failed to fetch records: {e}")

        if algo_info_box:
            st.info(algo_info_box)

        if display_data:
            df = pd.DataFrame(display_data)
            st.dataframe(df, use_container_width=True)

            # Direct Status update option for cabinet
            st.markdown("##### Review / Update Submission Status")
            uc1, uc2, uc3 = st.columns([2, 2, 1])
            with uc1:
                sub_ids = [d.get("submission_id") or d.get("registration_id") for d in display_data if d.get("submission_id") or d.get("registration_id")]
                chosen_sub = st.selectbox("Select Submission:", sub_ids, key="cab_rev_sub")
            with uc2:
                new_status = st.selectbox("Decision Status:", ["Approved", "Rejected"], key="cab_rev_status")
            with uc3:
                if st.button("Apply Decision", key="cab_apply_decision_btn"):
                    rev_res = requests.post(
                        f"{BACKEND_URL}/api/submissions/{chosen_sub}/review",
                        data={"status": new_status},
                        headers=headers,
                        timeout=5
                    )
                    if rev_res.status_code == 200:
                        st.success(f"Status for {chosen_sub} updated to {new_status}!")
                        st.rerun()
                    else:
                        st.error(rev_res.text)
        else:
            st.info("No records to display.")

    # =========================================================================
    # TAB 3: Mark Attendance
    # =========================================================================
    with tab_attendance:
        st.subheader("Mark Event Attendance")
        st.caption("Verify student presence at DUET Data Science Society workshops and summits.")

        try:
            ev_resp = requests.get(f"{BACKEND_URL}/api/events", headers=headers, timeout=5)
            events = ev_resp.json() if ev_resp.status_code == 200 else []
        except Exception:
            events = []

        if events:
            event_map = {f"{e.get('event_id')} - {e.get('title')} ({e.get('date')})": e.get('event_id') for e in events}
            selected_event_str = st.selectbox("Select Event:", list(event_map.keys()), key="cab_att_ev")
            selected_ev_id = event_map[selected_event_str]

            with st.form("mark_attendance_form"):
                ac1, ac2, ac3 = st.columns(3)
                with ac1:
                    att_roll = st.text_input("Student Roll Number *", placeholder="25F-DS-052").strip().upper()
                with ac2:
                    att_role = st.selectbox("Role *", ["Attendee", "Volunteer"])
                with ac3:
                    att_status = st.selectbox("Attendance Status *", ["Present", "Absent"])

                mark_btn = st.form_submit_button("Record Attendance", use_container_width=True)

            if mark_btn:
                if not att_roll:
                    st.error("Please enter a roll number.")
                else:
                    att_payload = {
                        "event_id": selected_ev_id,
                        "roll_no": att_roll,
                        "role": att_role,
                        "status": att_status
                    }
                    att_post = requests.post(f"{BACKEND_URL}/api/attendance", data=att_payload, headers=headers, timeout=5)
                    if att_post.status_code == 200:
                        st.success(f"Recorded attendance for {att_roll} ({att_status})!")
                    else:
                        detail = att_post.json().get("detail", att_post.text)
                        st.error(f"Failed to record attendance: {detail}")

            # Show current event attendance list
            st.markdown("##### Attendance Records for Event")
            try:
                all_att_resp = requests.get(f"{BACKEND_URL}/api/attendance", headers=headers, timeout=5)
                if all_att_resp.status_code == 200:
                    all_att = all_att_resp.json()
                    cur_ev_att = [a for a in all_att if a.get("event_id") == selected_ev_id]
                    if cur_ev_att:
                        st.dataframe(pd.DataFrame(cur_ev_att), use_container_width=True)
                    else:
                        st.info("No attendance recorded yet for this event.")
            except Exception:
                pass
        else:
            st.warning("No events available to mark attendance for.")

    # =========================================================================
    # TAB 4: Volunteer Task Assignments
    # =========================================================================
    with tab_assignments:
        st.subheader("Volunteer Task Assignments")
        st.caption("Coordinate duties, ushering, technical support, and registration desk for society events.")

        with st.form("create_assignment_form"):
            as_col1, as_col2 = st.columns(2)
            with as_col1:
                as_ev_str = st.selectbox("Event:", list(event_map.keys()) if events else ["No events"], key="asg_ev_sel")
                as_ev_id = event_map.get(as_ev_str, "")
                as_roll = st.text_input("Volunteer Roll Number *", placeholder="25F-DS-001").strip().upper()
            with as_col2:
                as_task = st.text_area("Task Description *", placeholder="Stage lighting, speaker escort, mic handling, attendee check-in")

            assign_btn = st.form_submit_button("Assign Task", use_container_width=True)

        if assign_btn:
            if not as_roll or not as_task:
                st.error("Please fill in the roll number and task description.")
            else:
                asg_payload = {
                    "event_id": as_ev_id,
                    "volunteer_roll_no": as_roll,
                    "task_description": as_task
                }
                asg_res = requests.post(f"{BACKEND_URL}/api/assignments", data=asg_payload, headers=headers, timeout=5)
                if asg_res.status_code == 200:
                    st.success(f"Task successfully assigned to volunteer {as_roll}!")
                else:
                    st.error(asg_res.text)

        # Show existing assignments
        st.markdown("##### Current Volunteer Assignments")
        try:
            asg_list_res = requests.get(f"{BACKEND_URL}/api/assignments", headers=headers, timeout=5)
            if asg_list_res.status_code == 200:
                asgs = asg_list_res.json()
                if asgs:
                    st.dataframe(pd.DataFrame(asgs), use_container_width=True)
                else:
                    st.info("No task assignments created yet.")
        except Exception:
            pass

    # =========================================================================
    # TAB 5: Reports Download
    # =========================================================================
    with tab_reports:
        st.subheader("Export Reports")
        st.caption("Download event participation, attendance, and registration sheets in CSV or Excel.")

        rep_col1, rep_col2 = st.columns(2)
        with rep_col1:
            st.markdown("##### Master Excel Workbook")
            st.caption("Download the complete records.xlsx workbook with all society data.")
            try:
                excel_dl = requests.get(f"{BACKEND_URL}/api/admin/download/records-excel", headers=headers, timeout=10)
                if excel_dl.status_code == 200:
                    st.download_button(
                        label="Download records.xlsx",
                        data=excel_dl.content,
                        file_name="ddss_records.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            except Exception:
                st.warning("Excel download not ready.")

        with rep_col2:
            st.markdown("##### Export Registrations CSV")
            try:
                regs_res = requests.get(f"{BACKEND_URL}/api/submissions/registrations", headers=headers, timeout=5)
                if regs_res.status_code == 200 and regs_res.json():
                    df_regs = pd.DataFrame(regs_res.json())
                    csv_data = df_regs.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Registrations CSV",
                        data=csv_data,
                        file_name="ddss_registrations.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            except Exception:
                st.warning("CSV export not ready.")
