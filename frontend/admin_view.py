"""
Admin Dashboard View for Streamlit Frontend.
Provides full administrative control: analytics charts, form management,
all data CRUD with handcrafted DSA search and sorting, ID card viewing,
cabinet account management, allowed roll numbers CSV upload,
Stack LIFO Undo, and Download Center.
"""

import io
import requests
import pandas as pd
import streamlit as st

from frontend.config import BACKEND_URL


def _get_headers(token: str) -> dict:
    return {"X-Auth-Token": token}


def render_admin_dashboard():
    user = st.session_state.get("user", {})
    token = st.session_state.get("token", "")
    headers = _get_headers(token)

    # Admin Header Banner with Undo quick button
    u_col1, u_col2 = st.columns([3, 1])
    with u_col1:
        st.markdown(
            f"""
            <div style="background-color: #0F172A; color: #FFFFFF; border-radius: 10px; padding: 14px 20px; margin-bottom: 16px;">
                <h2 style="color: #60A5FA; margin: 0;">Admin Control Center</h2>
                <div style="color: #94A3B8; font-size: 14px; margin-top: 2px;">
                    Full System Authority • Department of Data Science, DUET • Logged in as: <strong>{user.get('full_name')}</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with u_col2:
        # Undo Stack Widget
        try:
            stk_resp = requests.get(f"{BACKEND_URL}/api/admin/undo-stack", headers=headers, timeout=3)
            stack_size = stk_resp.json().get("size", 0) if stk_resp.status_code == 200 else 0
        except Exception:
            stack_size = 0

        st.markdown(f"**Undo Stack Depth:** `{stack_size}`")
        if st.button("Undo Last Action", help="Pops and reverts the most recent action from the LIFO Stack", use_container_width=True, key="undo_btn"):
            undo_res = requests.post(f"{BACKEND_URL}/api/admin/undo", headers=headers, timeout=5)
            if undo_res.status_code == 200:
                res_data = undo_res.json()
                st.success(f"Reverted: {res_data.get('message')}")
                st.rerun()
            else:
                detail = undo_res.json().get("detail", undo_res.text)
                st.warning(f"Undo: {detail}")

    # Tabs for Admin Functions
    tab_overview, tab_forms, tab_data, tab_cabinet, tab_allowed, tab_audit_downloads = st.tabs([
        "System Overview",
        "Form Management",
        "All Data & DSA Engine",
        "Cabinet Management",
        "Allowed Roll Numbers",
        "Audit & Download Center"
    ])

    # =========================================================================
    # TAB 1: System Overview & Charts
    # =========================================================================
    with tab_overview:
        st.subheader("Society Operations Overview")
        try:
            s_res = requests.get(f"{BACKEND_URL}/api/dashboard/stats", headers=headers, timeout=5)
            if s_res.status_code == 200:
                stats = s_res.json()

                # Visual Charts only (metrics already shown above)
                c_chart1, c_chart2 = st.columns(2)
                with c_chart1:
                    st.markdown("##### Registration Status Distribution")
                    reg_chart_data = pd.DataFrame({
                        "Status": ["Approved", "Pending", "Rejected"],
                        "Count": [
                            stats.get("registrations_approved", 0),
                            stats.get("registrations_pending", 0),
                            stats.get("registrations_rejected", 0)
                        ]
                    }).set_index("Status")
                    st.bar_chart(reg_chart_data, color="#2563EB")

                with c_chart2:
                    st.markdown("##### Society Participation Counts")
                    part_chart_data = pd.DataFrame({
                        "Category": ["Members", "Volunteers", "Attendees", "Attendance"],
                        "Total": [
                            stats.get("total_members", 0),
                            stats.get("total_volunteers", 0),
                            stats.get("total_attendees", 0),
                            stats.get("attendance_marked", 0)
                        ]
                    }).set_index("Category")
                    st.bar_chart(part_chart_data, color="#10B981")

        except Exception as e:
            st.error(f"Error loading dashboard statistics: {e}")

    # =========================================================================
    # TAB 2: Form Management (Create, Edit, One-Click Open/Close, Delete)
    # =========================================================================
    with tab_forms:
        st.subheader("Registration Forms Management")
        st.caption("Create Volunteer and Attendee forms, toggle open/close status manually with one click, or set automatic open/close schedules.")

        # Create New Form Expander
        with st.expander("Create New Event Form", expanded=False):
            # Fetch events for dropdown
            ev_res = requests.get(f"{BACKEND_URL}/api/events", headers=headers, timeout=5)
            ev_list = ev_res.json() if ev_res.status_code == 200 else []

            if not ev_list:
                st.warning("Please create an event before creating a form.")
            else:
                ev_map = {f"{e.get('event_id')} - {e.get('title')}": e for e in ev_list}
                with st.form("create_form_form"):
                    f_col1, f_col2 = st.columns(2)
                    with f_col1:
                        form_id_in = st.text_input("Form ID *", value=f"FORM-{len(ev_list)+1:03d}")
                        chosen_ev_str = st.selectbox("Event *", list(ev_map.keys()))
                        form_type_in = st.selectbox("Form Type *", ["Volunteer", "Attendee"])
                    with f_col2:
                        max_seats_in = st.number_input("Max Seats (Optional, 0 = unlimited)", min_value=0, value=0)
                        open_time_in = st.text_input("Open Date/Time (Optional: YYYY-MM-DD HH:MM:SS)", placeholder="e.g. 2026-10-24 09:00:00")
                        close_time_in = st.text_input("Close Date/Time (Optional: YYYY-MM-DD HH:MM:SS)", placeholder="e.g. 2026-11-10 18:00:00")

                    desc_in = st.text_area("Form Description *", placeholder="Detailed instructions displayed at the top of the student form.")
                    initial_open = st.checkbox("Open immediately", value=True)
                    submit_form_btn = st.form_submit_button("Create Form", use_container_width=True)

                if submit_form_btn:
                    chosen_ev = ev_map[chosen_ev_str]
                    new_form_payload = {
                        "form_id": form_id_in.strip(),
                        "event_id": chosen_ev.get("event_id"),
                        "event_title": chosen_ev.get("title"),
                        "form_type": form_type_in,
                        "description": desc_in.strip(),
                        "is_open_manual": initial_open,
                        "open_time": open_time_in.strip() if open_time_in.strip() else "",
                        "close_time": close_time_in.strip() if close_time_in.strip() else "",
                        "max_seats": int(max_seats_in) if max_seats_in > 0 else None,
                        "created_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    create_resp = requests.post(f"{BACKEND_URL}/api/forms", json=new_form_payload, headers=headers, timeout=5)
                    if create_resp.status_code == 200:
                        st.success(f"Form '{form_id_in}' created successfully!")
                        st.rerun()
                    else:
                        st.error(create_resp.text)

        # List Existing Forms
        st.markdown("##### Existing Forms List")
        f_list_resp = requests.get(f"{BACKEND_URL}/api/forms", headers=headers, timeout=5)
        forms_data = f_list_resp.json() if f_list_resp.status_code == 200 else []

        if forms_data:
            for f in forms_data:
                fid = f.get("form_id")
                is_op = f.get("computed_is_open", False)
                status_txt = f.get("status_message", "")
                man_open = str(f.get("is_open_manual", "True")).lower() in ["true", "1", "yes"]

                with st.container():
                    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
                    with fc1:
                        st.write(f"**{fid}** - {f.get('event_title')}")
                        st.caption(f"Type: **{f.get('form_type')}** | {f.get('description')}")
                    with fc2:
                        badge_color = "green" if is_op else "red"
                        st.markdown(f":{badge_color}[●] **{status_txt}**")
                        if f.get("max_seats"):
                            st.caption(f"Max Seats: {f.get('max_seats')}")
                    with fc3:
                        # One-click manual open/close toggle
                        toggle_label = "Close Form" if man_open else "Open Form"
                        if st.button(toggle_label, key=f"toggle_{fid}", use_container_width=True):
                            requests.put(
                                f"{BACKEND_URL}/api/forms/{fid}",
                                json={"is_open_manual": not man_open},
                                headers=headers,
                                timeout=5
                            )
                            st.rerun()
                    with fc4:
                        if st.button("Delete", key=f"del_f_{fid}", use_container_width=True):
                            requests.delete(f"{BACKEND_URL}/api/forms/{fid}", headers=headers, timeout=5)
                            st.rerun()
                    st.divider()
        else:
            st.info("No forms currently registered.")

    # =========================================================================
    # TAB 3: All Data Management with Handcrafted DSA Search & Sort
    # =========================================================================
    with tab_data:
        st.subheader("Master Database & DSA Engine")
        st.caption("Inspect and manage all Excel sheets with custom Singly Linked List, Array, Sorting and Searching algorithms.")

        dataset_options = ["Members", "Volunteers", "Attendees", "Events", "Attendance", "Assignments", "Cabinet Accounts"]
        chosen_sheet = st.selectbox("Select Dataset to Manage:", dataset_options, key="admin_ds_sel")
        ds_key = chosen_sheet.lower().replace(" accounts", "").replace(" ", "_")

        # DSA Searching Section
        st.markdown("##### Handcrafted Search Engine")
        sc1, sc2, sc3, sc4 = st.columns([2, 2, 2, 1])
        with sc1:
            possible_keys = {
                "members": ["name", "roll_no", "department", "member_id", "email"],
                "volunteers": ["candidate_name", "roll_no", "department", "event_title", "status", "submission_id"],
                "attendees": ["candidate_name", "roll_no", "department", "event_title", "status", "submission_id"],
                "events": ["title", "event_id", "date", "venue", "status"],
                "attendance": ["roll_no", "candidate_name", "event_title", "role", "status"],
                "assignments": ["volunteer_roll_no", "volunteer_name", "event_title", "status"],
                "cabinet": ["full_name", "username", "title", "role", "email"]
            }.get(ds_key, ["name", "roll_no"])
            adm_search_key = st.selectbox("Search Field:", possible_keys, key="adm_s_key")
        with sc2:
            adm_search_q = st.text_input("Search Value:", placeholder="Type to search...", key="adm_s_val")
        with sc3:
            adm_search_algo = st.selectbox("Algorithm:", ["Linear Search (O(n))", "Binary Search (O(log n))"], key="adm_s_algo")
        with sc4:
            adm_do_search = st.button("Run Search", key="adm_s_btn")

        # DSA Sorting Section
        st.markdown("##### Handcrafted Sorting Engine")
        so1, so2, so3, so4 = st.columns([2, 2, 2, 1])
        with so1:
            adm_sort_key = st.selectbox("Sort Key:", possible_keys, key="adm_sort_key")
        with so2:
            adm_sort_algo = st.selectbox("Algorithm:", ["Merge Sort (O(n log n))", "Quick Sort (O(n log n))", "Bubble Sort (O(n^2))", "Insertion Sort (O(n^2))"], key="adm_sort_algo")
        with so3:
            adm_sort_rev = st.selectbox("Order:", ["Ascending", "Descending"], key="adm_sort_dir")
        with so4:
            adm_do_sort = st.button("Run Sort", key="adm_sort_btn")

        records_to_display = None
        dsa_info = None

        if adm_do_search and adm_search_q:
            algo_p = "binary" if "Binary" in adm_search_algo else "linear"
            search_body = {
                "dataset": ds_key,
                "key": adm_search_key,
                "query": adm_search_q,
                "algorithm": algo_p,
                "partial": True
            }
            try:
                res = requests.post(f"{BACKEND_URL}/api/dsa/search", json=search_body, headers=headers, timeout=5)
                if res.status_code == 200:
                    rj = res.json()
                    dsa_info = f"**{rj.get('algorithm')}** ({rj.get('time_complexity')}) ran **{rj.get('comparisons')} comparisons** across {rj.get('total_items')} items. Found **{rj.get('count')} match(es)**."
                    records_to_display = rj.get("results", [])
                else:
                    st.error(res.text)
            except Exception as e:
                st.error(f"Search failed: {e}")

        elif adm_do_sort:
            algo_p = "merge"
            if "Quick" in adm_sort_algo:
                algo_p = "quick"
            elif "Bubble" in adm_sort_algo:
                algo_p = "bubble"
            elif "Insertion" in adm_sort_algo:
                algo_p = "insertion"

            sort_body = {
                "dataset": ds_key,
                "key": adm_sort_key,
                "algorithm": algo_p,
                "reverse": (adm_sort_rev == "Descending")
            }
            try:
                res = requests.post(f"{BACKEND_URL}/api/dsa/sort", json=sort_body, headers=headers, timeout=5)
                if res.status_code == 200:
                    rj = res.json()
                    dsa_info = f"**{rj.get('algorithm')}** ({rj.get('time_complexity')}) sorted {rj.get('total_items')} items in **{rj.get('time_taken_seconds')}s**."
                    records_to_display = rj.get("results", [])
                else:
                    st.error(res.text)
            except Exception as e:
                st.error(f"Sort failed: {e}")

        else:
            # Standard fetch
            ep_map = {
                "members": "/api/members",
                "volunteers": "/api/submissions/volunteers",
                "attendees": "/api/submissions/attendees",
                "events": "/api/events",
                "attendance": "/api/attendance",
                "assignments": "/api/assignments",
                "cabinet": "/api/admin/cabinet"
            }
            try:
                res = requests.get(f"{BACKEND_URL}{ep_map.get(ds_key, '/api/members')}", headers=headers, timeout=5)
                if res.status_code == 200:
                    records_to_display = res.json()
            except Exception as e:
                st.error(f"Failed to fetch data: {e}")

        if dsa_info:
            st.info(dsa_info)

        if records_to_display:
            df = pd.DataFrame(records_to_display)
            st.dataframe(df, use_container_width=True)

            # Actions section for selected record
            st.markdown("##### Record Actions & ID Card Inspection")
            id_col = "member_id" if ds_key == "members" else ("submission_id" if "volunteers" in ds_key or "attendees" in ds_key else ("event_id" if ds_key == "events" else "username"))
            if id_col in df.columns:
                rec_ids = df[id_col].dropna().tolist()
                act_c1, act_c2, act_c3 = st.columns([2, 1, 1])
                with act_c1:
                    chosen_rec_id = st.selectbox(f"Select Record by {id_col}:", rec_ids, key=f"sel_rec_{ds_key}")
                with act_c2:
                    if ds_key == "members":
                        if st.button("Delete Member", key="del_mem_btn", use_container_width=True):
                            requests.delete(f"{BACKEND_URL}/api/members/{chosen_rec_id}", headers=headers, timeout=5)
                            st.success(f"Deleted {chosen_rec_id}")
                            st.rerun()
                    elif ds_key == "events":
                        if st.button("Delete Event", key="del_ev_btn", use_container_width=True):
                            requests.delete(f"{BACKEND_URL}/api/events/{chosen_rec_id}", headers=headers, timeout=5)
                            st.success(f"Deleted {chosen_rec_id}")
                            st.rerun()
                    elif ds_key in ["volunteers", "attendees"]:
                        # View ID card image
                        target_row = next((r for r in records_to_display if r.get(id_col) == chosen_rec_id), None)
                        if target_row and target_row.get("id_card_file"):
                            img_path = target_row.get("id_card_file")
                            img_res = requests.get(f"{BACKEND_URL}/api/uploads/{img_path}", headers=headers, timeout=5)
                            if img_res.status_code == 200:
                                st.image(img_res.content, caption=f"ID Card: {chosen_rec_id} ({target_row.get('roll_no')})", width=250)
                            else:
                                st.warning("ID card image could not be loaded.")
                with act_c3:
                    if ds_key in ["volunteers", "attendees"]:
                        if st.button("Approve", key="adm_appr_btn", use_container_width=True):
                            requests.post(f"{BACKEND_URL}/api/submissions/{chosen_rec_id}/review", data={"status": "Approved"}, headers=headers, timeout=5)
                            st.rerun()
                        if st.button("Reject", key="adm_rej_btn", use_container_width=True):
                            requests.post(f"{BACKEND_URL}/api/submissions/{chosen_rec_id}/review", data={"status": "Rejected"}, headers=headers, timeout=5)
                            st.rerun()

            # Member Participation History Linked List Inspector
            if ds_key == "members":
                st.markdown("##### Member Participation History (Handcrafted Linked List)")
                rolls = [m.get("roll_no") for m in records_to_display if m.get("roll_no")]
                if rolls:
                    inspect_roll = st.selectbox("Select Member Roll Number:", rolls, key="hist_roll_sel")
                    hist_res = requests.get(f"{BACKEND_URL}/api/members/{inspect_roll}/history", headers=headers, timeout=5)
                    if hist_res.status_code == 200:
                        h_data = hist_res.json()
                        st.caption(f"Linked List Nodes Count: **{h_data.get('count')} event participation records**")
                        if h_data.get("history"):
                            st.dataframe(pd.DataFrame(h_data.get("history")), use_container_width=True)
                        else:
                            st.info("No recorded attendance nodes in linked list yet for this student.")

        else:
            st.info("No records found in this dataset.")

        # -----------------------------------------------------------------
        # Dataset management forms (add / edit / delete / status)
        # -----------------------------------------------------------------
        def _api_call(method, path, **kw):
            try:
                r = requests.request(method, f"{BACKEND_URL}{path}", headers=headers, timeout=5, **kw)
            except Exception as exc:
                st.error(f"Request failed: {exc}")
                return None
            if r.status_code == 200:
                return r
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            st.error(f"{detail}")
            return None

        if ds_key == "members":
            st.markdown("##### Manage Members")
            mem_list = requests.get(f"{BACKEND_URL}/api/members", headers=headers, timeout=5).json()
            with st.expander("Add New Member", expanded=False):
                with st.form("add_member_form"):
                    am1, am2 = st.columns(2)
                    with am1:
                        nm_id = st.text_input("Member ID *", value=f"MEM-{len(mem_list) + 1:03d}")
                        nm_name = st.text_input("Full Name *")
                        nm_roll = st.text_input("Roll Number *", placeholder="25F-DS-001")
                    with am2:
                        nm_phone = st.text_input("Contact Number *", placeholder="03001234567")
                        nm_dept = st.text_input("Department *", value="Data Science")
                        nm_email = st.text_input("Email", placeholder="25f-ds-001@students.duet.edu.pk")
                    add_mem_btn = st.form_submit_button("Add Member", use_container_width=True)
                if add_mem_btn:
                    if not (nm_id.strip() and nm_name.strip() and nm_roll.strip() and nm_phone.strip() and nm_dept.strip()):
                        st.error("Member ID, name, roll number, contact number and department are required.")
                    else:
                        payload = {
                            "member_id": nm_id.strip(),
                            "name": nm_name.strip(),
                            "roll_no": nm_roll.strip().upper(),
                            "phone": nm_phone.strip(),
                            "department": nm_dept.strip(),
                            "email": nm_email.strip(),
                            "status": "Active",
                            "joined_at": pd.Timestamp.now().strftime("%Y-%m-%d"),
                        }
                        if _api_call("POST", "/api/members", json=payload):
                            st.success(f"Member {nm_id.strip()} added.")
                            st.rerun()

            if mem_list:
                with st.expander("Edit Member", expanded=False):
                    em_map = {f"{m.get('member_id')} - {m.get('name')}": m for m in mem_list}
                    em_key = st.selectbox("Select Member:", list(em_map.keys()), key="edit_mem_sel")
                    em = em_map[em_key]
                    with st.form(f"edit_member_form_{em.get('member_id')}"):
                        ed1, ed2 = st.columns(2)
                        with ed1:
                            ed_name = st.text_input("Full Name", value=str(em.get("name", "")))
                            ed_phone = st.text_input("Contact Number", value=str(em.get("phone", "")))
                            ed_email = st.text_input("Email", value=str(em.get("email", "") or ""))
                        with ed2:
                            ed_dept = st.text_input("Department", value=str(em.get("department", "")))
                            status_opts = ["Active", "Inactive"]
                            cur_status = str(em.get("status", "Active"))
                            if cur_status not in status_opts:
                                status_opts.append(cur_status)
                            ed_status = st.selectbox("Status", status_opts, index=status_opts.index(cur_status))
                        save_mem_btn = st.form_submit_button("Save Changes", use_container_width=True)
                    if save_mem_btn:
                        updates = {
                            "name": ed_name.strip(),
                            "phone": ed_phone.strip(),
                            "email": ed_email.strip(),
                            "department": ed_dept.strip(),
                            "status": ed_status,
                        }
                        if _api_call("PUT", f"/api/members/{em.get('member_id')}", json=updates):
                            st.success("Member updated.")
                            st.rerun()

        elif ds_key == "events":
            st.markdown("##### Manage Events")
            ev_all = requests.get(f"{BACKEND_URL}/api/events", headers=headers, timeout=5).json()
            with st.expander("Create New Event", expanded=False):
                with st.form("create_event_form"):
                    ce1, ce2 = st.columns(2)
                    with ce1:
                        ev_id_in = st.text_input("Event ID *", value=f"EVT-{len(ev_all) + 1:03d}")
                        ev_title_in = st.text_input("Event Name *")
                        ev_venue_in = st.text_input("Venue *")
                        ev_status_in = st.selectbox("Status", ["Upcoming", "Ongoing", "Completed", "Cancelled"])
                    with ce2:
                        ev_date_in = st.date_input("Event Date *", key="ev_date_in")
                        ev_start_in = st.time_input("Start Time *", value=pd.Timestamp("10:00").time(), key="ev_start_in")
                        ev_end_in = st.time_input("End Time *", value=pd.Timestamp("12:00").time(), key="ev_end_in")
                    ev_desc_in = st.text_area("Description *")
                    create_ev_btn = st.form_submit_button("Create Event", use_container_width=True)
                if create_ev_btn:
                    if not (ev_id_in.strip() and ev_title_in.strip() and ev_venue_in.strip() and ev_desc_in.strip()):
                        st.error("Event ID, name, venue and description are required.")
                    else:
                        payload = {
                            "event_id": ev_id_in.strip(),
                            "title": ev_title_in.strip(),
                            "description": ev_desc_in.strip(),
                            "date": ev_date_in.strftime("%Y-%m-%d"),
                            "time": ev_start_in.strftime("%H:%M"),
                            "start_time": ev_start_in.strftime("%H:%M"),
                            "end_time": ev_end_in.strftime("%H:%M"),
                            "venue": ev_venue_in.strip(),
                            "status": ev_status_in,
                        }
                        if _api_call("POST", "/api/events", json=payload):
                            st.success(f"Event {ev_id_in.strip()} created.")
                            st.rerun()

            if ev_all:
                with st.expander("Edit Event", expanded=False):
                    ee_map = {f"{e.get('event_id')} - {e.get('title')}": e for e in ev_all}
                    ee_key = st.selectbox("Select Event:", list(ee_map.keys()), key="edit_ev_sel")
                    ee = ee_map[ee_key]
                    with st.form(f"edit_event_form_{ee.get('event_id')}"):
                        ex1, ex2 = st.columns(2)
                        with ex1:
                            ex_title = st.text_input("Event Name", value=str(ee.get("title", "")))
                            ex_venue = st.text_input("Venue", value=str(ee.get("venue", "")))
                            ex_date = st.text_input("Date (YYYY-MM-DD)", value=str(ee.get("date", "")))
                        with ex2:
                            ex_start = st.text_input("Start Time (HH:MM)", value=str(ee.get("start_time", "") or ee.get("time", "")))
                            ex_end = st.text_input("End Time (HH:MM)", value=str(ee.get("end_time", "") or ""))
                            st_opts = ["Upcoming", "Ongoing", "Completed", "Cancelled"]
                            cur_st = str(ee.get("status", "Upcoming"))
                            if cur_st not in st_opts:
                                st_opts.append(cur_st)
                            ex_status = st.selectbox("Status", st_opts, index=st_opts.index(cur_st))
                        ex_desc = st.text_area("Description", value=str(ee.get("description", "")))
                        save_ev_btn = st.form_submit_button("Save Changes", use_container_width=True)
                    if save_ev_btn:
                        updates = {
                            "title": ex_title.strip(),
                            "venue": ex_venue.strip(),
                            "date": ex_date.strip(),
                            "time": ex_start.strip(),
                            "start_time": ex_start.strip(),
                            "end_time": ex_end.strip(),
                            "status": ex_status,
                            "description": ex_desc.strip(),
                        }
                        if _api_call("PUT", f"/api/events/{ee.get('event_id')}", json=updates):
                            st.success("Event updated.")
                            st.rerun()

        elif ds_key == "attendance":
            st.markdown("##### Mark Attendance")
            ev_for_att = requests.get(f"{BACKEND_URL}/api/events", headers=headers, timeout=5).json()
            if ev_for_att:
                att_ev_map = {f"{e.get('event_id')} - {e.get('title')} ({e.get('date')})": e.get("event_id") for e in ev_for_att}
                with st.form("admin_mark_attendance_form"):
                    ma_ev = st.selectbox("Event *", list(att_ev_map.keys()))
                    ma1, ma2, ma3 = st.columns(3)
                    with ma1:
                        ma_roll = st.text_input("Student Roll Number *", placeholder="25F-DS-001")
                    with ma2:
                        ma_role = st.selectbox("Role *", ["Attendee", "Volunteer"])
                    with ma3:
                        ma_status = st.selectbox("Attendance Status *", ["Present", "Absent"])
                    mark_att_btn = st.form_submit_button("Record Attendance", use_container_width=True)
                if mark_att_btn:
                    if not ma_roll.strip():
                        st.error("Please enter a roll number.")
                    else:
                        payload = {
                            "event_id": att_ev_map[ma_ev],
                            "roll_no": ma_roll.strip().upper(),
                            "role": ma_role,
                            "status": ma_status,
                        }
                        if _api_call("POST", "/api/attendance", data=payload):
                            st.success(f"Recorded attendance for {ma_roll.strip().upper()} ({ma_status}).")
                            st.rerun()
            else:
                st.info("Create an event first to mark attendance.")

            st.markdown("##### Manage Attendance Records")
            att_all = requests.get(f"{BACKEND_URL}/api/attendance", headers=headers, timeout=5).json()
            if att_all:
                da_map = {
                    f"{a.get('attendance_id')} - {a.get('roll_no')} ({a.get('event_title')}, {a.get('status')})": a.get("attendance_id")
                    for a in att_all
                }
                da_key = st.selectbox("Select Attendance Record:", list(da_map.keys()), key="del_att_sel")
                if st.button("Delete Attendance Record", key="del_att_btn"):
                    if _api_call("DELETE", f"/api/attendance/{da_map[da_key]}"):
                        st.success("Attendance record deleted.")
                        st.rerun()
            else:
                st.info("No attendance records to manage.")

        elif ds_key == "assignments":
            st.markdown("##### Assign Task to Volunteer")
            ev_for_asg = requests.get(f"{BACKEND_URL}/api/events", headers=headers, timeout=5).json()
            vol_rows = requests.get(f"{BACKEND_URL}/api/submissions/volunteers", headers=headers, timeout=5).json()
            approved_vols = {}
            for v in vol_rows:
                if str(v.get("status", "")).lower() not in ("pending", "rejected"):
                    approved_vols[f"{v.get('roll_no')} - {v.get('candidate_name')}"] = v.get("roll_no")
            if not ev_for_asg:
                st.info("Create an event first to assign tasks.")
            elif not approved_vols:
                st.info("No approved volunteers yet. Approve a volunteer submission first.")
            else:
                asg_ev_map = {f"{e.get('event_id')} - {e.get('title')}": e.get("event_id") for e in ev_for_asg}
                with st.form("admin_assign_task_form"):
                    as_ev = st.selectbox("Event *", list(asg_ev_map.keys()))
                    as_vol = st.selectbox("Volunteer *", list(approved_vols.keys()))
                    as_task = st.text_area("Task Description *", placeholder="Registration desk, ushering, stage management")
                    assign_btn = st.form_submit_button("Assign Task", use_container_width=True)
                if assign_btn:
                    if not as_task.strip():
                        st.error("Please enter a task description.")
                    else:
                        payload = {
                            "event_id": asg_ev_map[as_ev],
                            "volunteer_roll_no": approved_vols[as_vol],
                            "task_description": as_task.strip(),
                        }
                        if _api_call("POST", "/api/assignments", data=payload):
                            st.success(f"Task assigned to {as_vol}.")
                            st.rerun()

            st.markdown("##### Manage Volunteer Assignments")
            asg_all = requests.get(f"{BACKEND_URL}/api/assignments", headers=headers, timeout=5).json()
            if asg_all:
                sa_map = {
                    f"{a.get('assignment_id')} - {a.get('volunteer_name')} ({a.get('event_title')}, {a.get('status')})": a
                    for a in asg_all
                }
                sa_key = st.selectbox("Select Assignment:", list(sa_map.keys()), key="asg_manage_sel")
                sa = sa_map[sa_key]
                ma1, ma2 = st.columns([2, 1])
                with ma1:
                    status_choices = ["Assigned", "In Progress", "Completed"]
                    cur_as = str(sa.get("status", "Assigned"))
                    if cur_as not in status_choices:
                        status_choices.append(cur_as)
                    new_as_status = st.selectbox("Update Status:", status_choices, index=status_choices.index(cur_as), key="asg_status_sel")
                    if st.button("Update Assignment Status", key="asg_status_btn"):
                        if _api_call("PUT", f"/api/assignments/{sa.get('assignment_id')}/status", data={"status": new_as_status}):
                            st.success("Assignment status updated.")
                            st.rerun()
                with ma2:
                    st.write("")
                    st.write("")
                    if st.button("Delete Assignment", key="asg_del_btn"):
                        if _api_call("DELETE", f"/api/assignments/{sa.get('assignment_id')}"):
                            st.success("Assignment deleted.")
                            st.rerun()
            else:
                st.info("No assignments to manage.")

        # Event-wise member and volunteer lists
        with st.expander("Event-wise Member, Volunteer and Attendance Lists", expanded=False):
            ev_for_lists = requests.get(f"{BACKEND_URL}/api/events", headers=headers, timeout=5).json()
            if ev_for_lists:
                el_map = {f"{e.get('event_id')} - {e.get('title')}": e.get("event_id") for e in ev_for_lists}
                el_key = st.selectbox("Select Event:", list(el_map.keys()), key="event_lists_sel")
                part_res = requests.get(f"{BACKEND_URL}/api/events/{el_map[el_key]}/participants", headers=headers, timeout=5)
                if part_res.status_code == 200:
                    part = part_res.json()
                    for label, key in [
                        ("Volunteers", "volunteers"),
                        ("Attendees", "attendees"),
                        ("Attendance", "attendance"),
                        ("Volunteer Assignments", "assignments"),
                    ]:
                        st.markdown(f"**{label}** ({len(part.get(key, []))})")
                        if part.get(key):
                            st.dataframe(pd.DataFrame(part[key]), use_container_width=True)
                        else:
                            st.caption(f"No {label.lower()} recorded for this event.")
            else:
                st.info("No events available.")

    # =========================================================================
    # TAB 4: Cabinet Accounts Management (9 accounts + Admin)
    # =========================================================================
    with tab_cabinet:
        st.subheader("Cabinet Portfolio Management")
        st.caption("Manage society leadership positions. Update titles, full names, active statuses, or reset passwords.")

        cab_resp = requests.get(f"{BACKEND_URL}/api/admin/cabinet", headers=headers, timeout=5)
        cab_users = cab_resp.json() if cab_resp.status_code == 200 else []

        if cab_users:
            st.dataframe(pd.DataFrame(cab_users), use_container_width=True)

            st.markdown("##### Edit Cabinet Member or Reset Password")
            u_names = [u.get("username") for u in cab_users]
            ed_col1, ed_col2, ed_col3 = st.columns(3)
            with ed_col1:
                sel_cab_user = st.selectbox("Select Cabinet Member:", u_names, key="sel_cab_usr")
                cur_user = next((u for u in cab_users if u.get("username") == sel_cab_user), {})
                new_fn = st.text_input("Full Name", value=cur_user.get("full_name", ""))
            with ed_col2:
                new_title = st.text_input("Cabinet Title / Portfolio", value=cur_user.get("title", ""))
                new_st = st.selectbox("Account Status", ["Active", "Inactive"], index=0 if cur_user.get("status") == "Active" else 1)
            with ed_col3:
                reset_pwd_val = st.text_input("Reset Password (Optional)", placeholder="New password...", type="password")

            if st.button("Save Account Changes", use_container_width=True):
                update_payload = {
                    "full_name": new_fn.strip(),
                    "title": new_title.strip(),
                    "status": new_st
                }
                if reset_pwd_val.strip():
                    update_payload["password"] = reset_pwd_val.strip()

                up_res = requests.put(f"{BACKEND_URL}/api/admin/cabinet/{sel_cab_user}", json=update_payload, headers=headers, timeout=5)
                if up_res.status_code == 200:
                    st.success(f"Cabinet account '{sel_cab_user}' updated!")
                    st.rerun()
                else:
                    st.error(up_res.text)

        # Add New Cabinet Member
        with st.expander("Add New Cabinet Position"):
            with st.form("add_cabinet_form"):
                ac1, ac2 = st.columns(2)
                with ac1:
                    new_c_user = st.text_input("Username *", placeholder="e.g. dirpr")
                    new_c_fn = st.text_input("Full Name *", placeholder="e.g. Daniyal Khan")
                    new_c_title = st.text_input("Title *", placeholder="e.g. Director PR")
                with ac2:
                    new_c_pwd = st.text_input("Password *", type="password")
                    new_c_email = st.text_input("Email", placeholder="daniyal@duet.edu.pk")
                    new_c_phone = st.text_input("Phone", placeholder="03001234567")

                add_cab_btn = st.form_submit_button("Register Cabinet Member", use_container_width=True)

            if add_cab_btn:
                if not new_c_user or not new_c_fn or not new_c_title or not new_c_pwd:
                    st.error("Please fill in all required fields.")
                else:
                    add_cab_payload = {
                        "username": new_c_user.strip().lower(),
                        "full_name": new_c_fn.strip(),
                        "title": new_c_title.strip(),
                        "password": new_c_pwd.strip(),
                        "email": new_c_email.strip(),
                        "phone": new_c_phone.strip()
                    }
                    nc_res = requests.post(f"{BACKEND_URL}/api/admin/cabinet", json=add_cab_payload, headers=headers, timeout=5)
                    if nc_res.status_code == 200:
                        st.success(f"Registered cabinet account '{new_c_user}'!")
                        st.rerun()
                    else:
                        st.error(nc_res.text)

    # =========================================================================
    # TAB 5: Allowed Roll Numbers Management
    # =========================================================================
    with tab_allowed:
        st.subheader("Allowed University Data Science Roll Numbers")
        st.caption("Only students present in this verified list and matching the regex `^\\d{2}F-DS-\\d{2,3}$` can submit forms.")

        rolls_resp = requests.get(f"{BACKEND_URL}/api/admin/allowed-rolls", headers=headers, timeout=5)
        if rolls_resp.status_code == 200:
            roll_data = rolls_resp.json()
            st.write(f"Total Enrolled Students: **{roll_data.get('count')}**")

            # Upload CSV
            st.markdown("##### Upload New Allowed Roll Numbers CSV")
            st.caption("Upload a CSV file containing roll numbers (e.g. 25F-DS-052) to update the allowed roll numbers.")
            uploaded_csv = st.file_uploader("Select CSV file", type=["csv"], key="roll_csv_uploader")
            if uploaded_csv and st.button("Update Allowed Roll Numbers"):
                csv_files = {"file": (uploaded_csv.name, uploaded_csv.getvalue(), "text/csv")}
                up_roll_res = requests.post(f"{BACKEND_URL}/api/admin/upload-allowed-rolls", files=csv_files, headers=headers, timeout=5)
                if up_roll_res.status_code == 200:
                    st.success(up_roll_res.json().get("message", "Allowed roll numbers updated."))
                    st.rerun()
                else:
                    st.error(up_roll_res.text)

            # Display allowed roll numbers in compact columns
            rolls_list = roll_data.get("allowed_roll_numbers", [])
            with st.expander("View All Allowed Roll Numbers", expanded=False):
                st.dataframe(pd.DataFrame({"Roll Number": rolls_list}), use_container_width=True)

    # =========================================================================
    # TAB 6: Audit Log & Download Center
    # =========================================================================
    with tab_audit_downloads:
        st.subheader("Audit Log & System Export Center")
        st.caption("Download master databases, submitted ID cards, or inspect the continuous audit log.")

        # Event-specific Excel Download & Reset
        st.markdown("##### Event Data Download & Reset")
        st.caption("Download a specific event's data as Excel. **All stored data for that event will be cleared after download.**")
        try:
            forms_for_dl = requests.get(f"{BACKEND_URL}/api/forms", headers=headers, timeout=5)
            if forms_for_dl.status_code == 200:
                dl_forms = forms_for_dl.json()
                if dl_forms:
                    dl_form_map = {f"{f.get('form_id')} - {f.get('event_title')}": f.get('form_id') for f in dl_forms}
                    selected_dl_form = st.selectbox("Select Event/Form to Download:", list(dl_form_map.keys()), key="dl_event_sel")
                    dl_form_id = dl_form_map[selected_dl_form]
                    exp_res = requests.get(f"{BACKEND_URL}/api/admin/export/event-excel/{dl_form_id}", headers=headers, timeout=5)
                    if exp_res.status_code == 200:
                        dl_clicked = st.download_button(
                            "Download Event Excel & Clear Data",
                            data=exp_res.content,
                            file_name=f"event_{dl_form_id}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            key=f"dl_btn_{dl_form_id}"
                        )
                        if dl_clicked:
                            requests.post(f"{BACKEND_URL}/api/admin/events/{dl_form_id}/clear-data", headers=headers, timeout=5)
                            st.success(f"Event data successfully downloaded! All stored data for '{selected_dl_form}' has been cleared.")
                            st.rerun()
                    else:
                        st.info("No submission data recorded yet for this event.")
                else:
                    st.info("No forms available for download.")
        except Exception as e:
            st.error(f"Error loading forms: {e}")

        st.divider()

        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            st.markdown("##### Master records.xlsx")
            st.caption("Complete Excel database with all 9 sheets.")
            ex_res = requests.get(f"{BACKEND_URL}/api/admin/download/records-excel", headers=headers, timeout=10)
            if ex_res.status_code == 200:
                st.download_button(
                    "Download records.xlsx",
                    data=ex_res.content,
                    file_name="records.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        with dc2:
            st.markdown("##### ID Cards Archive (ZIP)")
            st.caption("All candidate student ID photos in a single ZIP.")
            zip_res = requests.get(f"{BACKEND_URL}/api/admin/download/id-cards-zip", headers=headers, timeout=10)
            if zip_res.status_code == 200:
                st.download_button(
                    "Download ID Cards (ZIP)",
                    data=zip_res.content,
                    file_name="ddss_id_cards.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        with dc3:
            st.markdown("##### Audit Log File")
            st.caption("Direct download of activity_log.txt.")
            log_res = requests.get(f"{BACKEND_URL}/api/admin/download/activity-log", headers=headers, timeout=5)
            if log_res.status_code == 200:
                st.download_button(
                    "Download activity_log.txt",
                    data=log_res.content,
                    file_name="activity_log.txt",
                    mime="text/plain",
                    use_container_width=True
                )

        st.divider()
        st.markdown("##### Recent Audit Trail (activity_log.txt)")
        audit_res = requests.get(f"{BACKEND_URL}/api/admin/audit-log?limit=80", headers=headers, timeout=5)
        if audit_res.status_code == 200:
            lines = audit_res.json().get("logs", [])
            if lines:
                # Parse lines into structured dataframe
                log_entries = []
                for l in reversed(lines):
                    parts = l.split(" | ")
                    if len(parts) >= 4:
                        log_entries.append({
                            "Timestamp": parts[0],
                            "Actor / Roll Number": parts[1],
                            "Action Type": parts[2],
                            "Details": " | ".join(parts[3:])
                        })
                    else:
                        log_entries.append({"Raw Log": l})

                st.dataframe(pd.DataFrame(log_entries), use_container_width=True)
            else:
                st.info("No activity logged yet.")
