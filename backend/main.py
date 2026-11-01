"""
FastAPI Backend Application for DDSS.
Exposes REST endpoints for Authentication, Dashboard Analytics,
DSA operations (LinkedList, Array, Queue, Stack, Sorts, Searches),
Event and Form management, Submissions, Attendance, and File Handling.
"""

import os
import io
import json
import time
import uuid
import csv
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import (
    FastAPI, HTTPException, Depends, status, UploadFile, File, Form, Header
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image

from backend import auth
from backend import storage
from backend import dsa
from backend.models import (
    LoginRequest, LoginResponse, MemberModel, EventModel, FormModel,
    SubmissionRecord, AttendanceRecord, AssignmentRecord,
    CabinetAccountCreate, CabinetAccountUpdate, SearchRequest, SortRequest
)

from contextlib import asynccontextmanager


def _allowed_origins() -> list[str]:
    """Build CORS origins from the environment plus local development origins."""
    local_origins = {
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://ddss-project.vercel.app",
        "https://ddss-project-git-main-alishan-portfolio.vercel.app",
    }
    configured = {
        origin.strip().rstrip("/")
        for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if origin.strip() and origin.strip() != "*"
    }
    return sorted(local_origins | configured)


ALLOWED_ORIGIN_REGEX = r"^https://[a-z0-9-]+(?:-[a-z0-9-]+)*\.vercel\.app$"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes storage, loads workbook, populates DSA structures."""
    storage.init_storage()
    yield

app = FastAPI(
    title="DDSS - Dawood Data Science Society API",
    description="Backend API for DUET Data Science Society Member & Volunteer Management System",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Also ensure storage is initialized immediately upon import
storage.init_storage()


@app.get("/")
def root():
    return {"status": "online", "message": "DDSS API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/admin/storage-health")
def storage_health(user: dict = Depends(auth.require_role(["admin"]))):
    """Verifies private Blob access without touching application records."""
    try:
        return storage.blob_storage.health_check()
    except storage.blob_storage.BlobStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Persistent file storage health check failed.",
        ) from exc


# ============================================================================
# Helper Functions
# ============================================================================

def is_form_open(form: Dict[str, Any]) -> tuple[bool, str]:
    """
    Evaluates manual toggle, automatic open/close dates, and seat caps.
    Returns (is_open, status_message).
    """
    is_open_man = str(form.get("is_open_manual", "True")).strip().lower() in ["true", "1", "yes"]
    if not is_open_man:
        return False, "This form is closed."

    now = datetime.now()
    open_time_str = str(form.get("open_time", "")).strip()
    close_time_str = str(form.get("close_time", "")).strip()

    if open_time_str:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                open_dt = datetime.strptime(open_time_str, fmt)
                if now < open_dt:
                    return False, f"Opens on {open_time_str}"
                break
            except ValueError:
                pass

    if close_time_str:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                close_dt = datetime.strptime(close_time_str, fmt)
                if now > close_dt:
                    return False, f"This form closed on {close_time_str}."
                break
            except ValueError:
                pass

    # Check max seats
    max_seats_val = form.get("max_seats")
    if max_seats_val is not None and str(max_seats_val).strip() not in ["", "None"]:
        try:
            limit = int(max_seats_val)
            regs = storage.get_registrations()
            count = sum(1 for r in regs if r.get("form_id") == form.get("form_id"))
            if count >= limit:
                return False, "Registrations full."
        except ValueError:
            pass

    return True, "Form is currently open."


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/api/auth/login", response_model=LoginResponse)
def login(creds: LoginRequest):
    """Authenticates admin or cabinet members."""
    username = creds.username.strip().lower()
    accounts = storage.get_cabinet_accounts()
    matches = [
        acc for acc in accounts
        if str(acc.get("username", "")).strip().lower() == username
    ]

    if len(matches) != 1:
        storage.log_activity(creds.username, "FAILED_LOGIN", f"Login failed: username '{creds.username}' not found.")
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    account = matches[0]

    if account.get("status", "Active").lower() != "active":
        storage.log_activity(creds.username, "FAILED_LOGIN", f"Login rejected: account '{creds.username}' is deactivated.")
        raise HTTPException(status_code=403, detail="Account is deactivated. Contact administrator.")

    salt = account.get("salt", "")
    expected_hash = account.get("password_hash", "")
    if not auth.verify_password(creds.password, salt, expected_hash):
        storage.log_activity(creds.username, "FAILED_LOGIN", f"Login failed: invalid password for '{creds.username}'.")
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    role = str(account.get("role", "cabinet")).strip().lower()
    if role not in {"admin", "cabinet"}:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = auth.create_session(
        username=account.get("username"),
        role=role,
        full_name=account.get("full_name"),
        title=account.get("title", "")
    )
    storage.log_activity(account.get("username"), "LOGIN", f"User logged in successfully with role '{role}'.")

    return LoginResponse(
        token=token,
        username=account.get("username"),
        role=role,
        full_name=account.get("full_name"),
        title=account.get("title", "")
    )


@app.post("/api/auth/logout")
def logout(user: dict = Depends(auth.get_current_user_from_header), authorization: Optional[str] = Header(None), x_auth_token: Optional[str] = Header(None)):
    """Logs out and invalidates the session token."""
    token = x_auth_token or (authorization.split()[1] if authorization and " " in authorization else authorization)
    if token:
        auth.invalidate_session(token)
    storage.log_activity(user.get("username", "USER"), "LOGOUT", "User logged out.")
    return {"message": "Logged out successfully."}


@app.get("/api/auth/me")
def get_current_profile(user: dict = Depends(auth.get_current_user_from_header)):
    return user


# ============================================================================
# Public Endpoints (Student Form & Events)
# ============================================================================

@app.get("/api/public/forms")
def list_public_forms():
    """Lists available registration forms with dynamic open/closed status."""
    forms = storage.get_forms()
    result = []
    for f in forms:
        f_copy = dict(f)
        is_open, status_text = is_form_open(f)
        f_copy["computed_is_open"] = is_open
        f_copy["status_message"] = status_text
        result.append(f_copy)
    return result


@app.get("/api/public/forms/{form_id}")
def get_public_form(form_id: str):
    """Retrieves single form by ID with status."""
    forms = storage.get_forms()
    for f in forms:
        if f.get("form_id", "").strip().lower() == form_id.strip().lower():
            f_copy = dict(f)
            is_open, status_text = is_form_open(f)
            f_copy["computed_is_open"] = is_open
            f_copy["status_message"] = status_text
            return f_copy
    raise HTTPException(status_code=404, detail="Form not found.")


@app.post("/api/public/submit")
async def submit_student_form(
    form_id: str = Form(...),
    candidate_name: str = Form(...),
    roll_no: str = Form(...),
    phone_no: str = Form(...),
    department: str = Form(...),
    email: str = Form(""),
    university_email: str = Form(...),
    id_card_picture: UploadFile = File(...)
):
    """
    Handles student registration submission for Volunteer or Attendee form.
    Validates name, roll number against allowed list, phone number, and ID image.
    Enforces form open state, duplicate submission checks, and image constraints.
    """
    # 1. Fetch form
    allowed_departments = {
        "Data Science",
        "Computer Science",
        "Software Engineering",
        "Artificial Intelligence",
        "Cyber Security",
        "Telecommunication",
    }
    if department.strip() not in allowed_departments:
        raise HTTPException(status_code=400, detail="Invalid department.")

    forms = storage.get_forms()
    target_form = None
    for f in forms:
        if f.get("form_id", "").strip().lower() == form_id.strip().lower():
            target_form = f
            break

    if not target_form:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' does not exist.")

    # 2. Check if form is currently open
    is_open, reason = is_form_open(target_form)
    if not is_open:
        storage.log_activity(roll_no, "REJECTED_SUBMISSION_FORM_CLOSED", f"Submission to form {form_id} rejected: {reason}")
        raise HTTPException(status_code=400, detail=f"Form is closed for submissions: {reason}")

    # 3. Validate Roll Number format and allowed list
    clean_roll = roll_no.strip().upper()
    is_valid_roll, roll_err = auth.is_roll_number_allowed(clean_roll)
    if not is_valid_roll:
        storage.log_activity(clean_roll, "REJECTED_SUBMISSION_INVALID_ROLL", roll_err)
        raise HTTPException(status_code=400, detail=roll_err)

    # 4. Check Duplicate Submission for this form
    all_regs = storage.get_registrations()
    for r in all_regs:
        if (r.get("form_id", "").strip().lower() == form_id.strip().lower() and
                r.get("roll_no", "").strip().upper() == clean_roll):
            err_msg = "An application for this roll number has already been submitted for the selected form."
            storage.log_activity(clean_roll, "REJECTED_SUBMISSION_DUPLICATE", err_msg)
            raise HTTPException(status_code=400, detail=err_msg)

    # 5. Validate Name
    candidate_name = auth.normalize_candidate_name(candidate_name)
    is_valid_name, name_err = auth.validate_candidate_name(candidate_name)
    if not is_valid_name:
        raise HTTPException(status_code=400, detail=name_err)

    # 6. Validate Phone
    is_valid_phone, phone_err = auth.validate_phone_number(phone_no)
    if not is_valid_phone:
        raise HTTPException(status_code=400, detail=phone_err)

    # 6b. Validate University Email (must be unique and match DUET format)
    clean_univ_email = university_email.strip().lower()
    clean_email = email.strip() if email and email.strip() else clean_univ_email
    is_valid_email, email_err = auth.validate_university_email(clean_univ_email, clean_roll)
    if not is_valid_email:
        raise HTTPException(status_code=400, detail=email_err)

    # Check university email uniqueness across all registrations for this form
    for r in all_regs:
        if r.get("form_id", "").strip().lower() == form_id.strip().lower():
            reg_ue = r.get("university_email", "").strip().lower()
            reg_em = r.get("email", "").strip().lower()
            if (reg_ue and reg_ue == clean_univ_email) or (reg_em and reg_em == clean_univ_email):
                raise HTTPException(
                    status_code=400,
                    detail=f"University email '{clean_univ_email}' has already been used for a submission on this form."
                )

    # 7. Validate ID Card Image (Size & Pillow real format)
    # 80 KB = 81,920 bytes
    MAX_SIZE = 81920
    file_bytes = await id_card_picture.read()
    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Image must be 80 KB or smaller."
        )

    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
        img_format = (img.format or "").upper()
        if img_format not in ["JPEG", "JPG", "PNG"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '{img_format}'. Only JPG, JPEG, and PNG images are accepted."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"The uploaded file is not a valid or readable image: {str(e)}"
        )

    # 8. Save ID Card Image to uploads/<form_id>/<uuid>.<ext>
    ext = "png" if img_format == "PNG" else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_reference = f"{form_id}/{filename}"
    try:
        upload_reference = storage.save_upload(
            file_bytes,
            form_id,
            filename,
            id_card_picture.content_type or "application/octet-stream",
        )
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="Submission could not be saved because persistent file storage is temporarily unavailable. Please try again later.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Submission could not be saved because persistent file storage is temporarily unavailable. Please try again later.",
        ) from exc

    # 9. Create Submission Record
    form_type = target_form.get("form_type", "Attendee")
    prefix = "VOL" if form_type.lower() == "volunteer" else "ATT"
    ref_id = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    submission_dict = {
        "submission_id": ref_id,
        "form_id": form_id,
        "event_title": target_form.get("event_title", ""),
        "candidate_name": candidate_name,
        "roll_no": clean_roll,
        "phone_no": phone_no.strip(),
        "department": department.strip(),
        "email": clean_email,
        "university_email": clean_univ_email,
        "id_card_file": upload_reference,
        "submitted_at": now_str,
        "status": "Pending",
        "reviewed_by": "Unassigned"
    }

    try:
        ok, msg = storage.add_submission(submission_dict, form_type)
    except Exception as exc:
        try:
            storage.delete_upload(upload_reference)
        except OSError:
            pass
        raise HTTPException(
            status_code=500,
            detail="Registration could not be saved because the storage layer failed."
        ) from exc
    if not ok:
        try:
            storage.delete_upload(upload_reference)
        except OSError:
            pass
        raise HTTPException(
            status_code=503,
            detail=(
                "Submission could not be saved because persistent file storage is temporarily unavailable. "
                "Please try again later."
                if "storage" in msg.lower() or "save" in msg.lower()
                else msg
            ),
        )

    return {
        "success": True,
        "reference_number": ref_id,
        "form_type": form_type,
        "event_title": target_form.get("event_title"),
        "candidate_name": candidate_name,
        "roll_no": clean_roll,
        "message": f"Application submitted successfully! Your reference ID is {ref_id}."
    }


# ============================================================================
# Private ID Card Images & File Serving
# ============================================================================

@app.get("/api/uploads/{file_path:path}")
def get_uploaded_image(
    file_path: str,
    user: dict = Depends(auth.get_current_user_from_header)
):
    """
    Serves ID card pictures.
    Private: restricted strictly to authenticated Admin and Cabinet members.
    """
    if storage.is_vercel_runtime() and getattr(storage, "_BLOB_RUNTIME", False):
        try:
            return StreamingResponse(
                io.BytesIO(storage.read_upload(file_path)),
                media_type="application/octet-stream",
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Persistent file storage is unavailable.") from exc
    uploads_root = storage.UPLOADS_DIR.resolve()
    safe_path = (uploads_root / file_path).resolve()
    try:
        safe_path.relative_to(uploads_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied.")
    if not safe_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(safe_path)


# ============================================================================
# Analytics & Overview Dashboard (Admin & Cabinet)
# ============================================================================

@app.get("/api/dashboard/stats")
def get_dashboard_stats(user: dict = Depends(auth.get_current_user_from_header)):
    """Overview statistics for dashboard widgets and charts."""
    members = storage.get_members()
    volunteers = storage.get_volunteers()
    attendees = storage.get_attendees()
    events = storage.get_events()
    forms = storage.get_forms()
    attendance = storage.get_attendance()
    assignments = storage.get_assignments()

    open_forms = 0
    closed_forms = 0
    for f in forms:
        is_op, _ = is_form_open(f)
        if is_op:
            open_forms += 1
        else:
            closed_forms += 1

    all_submissions = volunteers + attendees
    pending = sum(1 for s in all_submissions if s.get("status", "").lower() == "pending")
    approved = sum(1 for s in all_submissions if s.get("status", "").lower() == "approved")
    rejected = sum(1 for s in all_submissions if s.get("status", "").lower() == "rejected")

    present_attendance = sum(1 for a in attendance if a.get("status", "").lower() == "present")

    return {
        "total_members": len(members),
        "total_volunteers": len(volunteers),
        "total_attendees": len(attendees),
        "total_events": len(events),
        "forms_open": open_forms,
        "forms_closed": closed_forms,
        "registrations_total": len(all_submissions),
        "registrations_pending": pending,
        "registrations_approved": approved,
        "registrations_rejected": rejected,
        "attendance_marked": len(attendance),
        "attendance_present": present_attendance,
        "total_assignments": len(assignments),
        "queue_size": storage.submissions_queue.size(),
        "undo_stack_size": storage.undo_stack.size()
    }


# ============================================================================
# Queue Endpoints (FIFO - Handcrafted)
# ============================================================================

@app.get("/api/queue")
def get_queue_items(user: dict = Depends(auth.get_current_user_from_header)):
    """Returns pending submissions in FIFO arrival order."""
    return {
        "size": storage.submissions_queue.size(),
        "items": storage.submissions_queue.to_list()
    }


@app.get("/api/queue/peek")
def peek_queue(user: dict = Depends(auth.get_current_user_from_header)):
    """Peeks at the next submission waiting at the front of the queue."""
    item = storage.submissions_queue.peek()
    return {"item": item}


@app.post("/api/queue/process")
def process_queue_submission(
    decision: str = Form(...),  # "Approved" or "Rejected"
    user: dict = Depends(auth.get_current_user_from_header)
):
    """
    Dequeues the oldest pending submission from the FIFO queue and applies approval/rejection.
    Available to both Admin and Cabinet members.
    """
    if storage.submissions_queue.is_empty():
        raise HTTPException(status_code=400, detail="Queue is empty. No pending submissions.")

    submission = storage.submissions_queue.dequeue()
    sub_id = submission.get("submission_id")
    is_vol = "VOL" in sub_id

    reviewer = f"{user.get('full_name')} ({user.get('username')})"
    ok, msg = storage.update_submission_status(
        submission_id=sub_id,
        new_status=decision,
        reviewed_by=reviewer,
        is_volunteer=is_vol
    )
    if not ok:
        # Re-enqueue if failure
        storage.submissions_queue.enqueue(submission)
        raise HTTPException(status_code=500, detail=msg)

    return {
        "success": True,
        "submission_id": sub_id,
        "decision": decision,
        "message": msg
    }


# ============================================================================
# Stack Endpoints (Undo LIFO - Admin Only)
# ============================================================================

@app.post("/api/admin/undo")
def undo_action(user: dict = Depends(auth.require_role(["admin"]))):
    """Pops and reverses the last recorded admin operation using Stack (LIFO)."""
    ok, msg, action = storage.undo_last_action(actor=user.get("username", "admin"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "action": action}


@app.get("/api/admin/undo-stack")
def get_undo_stack(user: dict = Depends(auth.require_role(["admin"]))):
    """Inspects the current state of the Undo Stack."""
    return {
        "size": storage.undo_stack.size(),
        "items": storage.undo_stack.to_list()
    }


# ============================================================================
# DSA Searching and Sorting Endpoints
# ============================================================================

def _get_dataset(dataset_name: str) -> List[Dict[str, Any]]:
    name = dataset_name.lower().strip()
    if name == "members":
        return storage.get_members()
    elif name == "volunteers":
        return storage.get_volunteers()
    elif name == "attendees":
        return storage.get_attendees()
    elif name == "events":
        return storage.get_events()
    elif name == "forms":
        return storage.get_forms()
    elif name == "registrations":
        return storage.get_registrations()
    elif name == "attendance":
        return storage.get_attendance()
    elif name == "cabinet":
        return storage.get_cabinet_accounts()
    elif name == "assignments":
        return storage.get_assignments()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown dataset '{dataset_name}'.")


@app.post("/api/dsa/search")
def search_records(req: SearchRequest, user: dict = Depends(auth.get_current_user_from_header)):
    """
    Executes Linear Search or Binary Search on dataset.
    Returns matched results, comparisons count, and algorithm metadata.
    """
    data = _get_dataset(req.dataset)

    if req.algorithm.lower() == "binary":
        # Binary search requires sorted data by key
        sorted_data, _ = dsa.merge_sort(data, key=req.key)
        matched_item, comparisons = dsa.binary_search(sorted_data, key=req.key, target_val=req.query)
        results = [matched_item] if matched_item else []
        return {
            "algorithm": "Binary Search",
            "time_complexity": "O(log n)",
            "key": req.key,
            "query": req.query,
            "comparisons": comparisons,
            "total_items": len(data),
            "count": len(results),
            "results": results
        }
    else:
        # Linear search
        results, comparisons = dsa.linear_search(data, key=req.key, query=req.query, partial=req.partial)
        return {
            "algorithm": "Linear Search",
            "time_complexity": "O(n)",
            "key": req.key,
            "query": req.query,
            "comparisons": comparisons,
            "total_items": len(data),
            "count": len(results),
            "results": results
        }


@app.post("/api/dsa/sort")
def sort_records(req: SortRequest, user: dict = Depends(auth.get_current_user_from_header)):
    """
    Executes Bubble, Insertion, Merge, or Quick sort on dataset.
    Returns sorted list, algorithm name, complexity, and elapsed time in seconds.
    """
    data = _get_dataset(req.dataset)
    algo = req.algorithm.lower().strip()

    if algo == "bubble":
        sorted_arr, elapsed = dsa.bubble_sort(data, key=req.key, reverse=req.reverse)
        complexity = "O(n^2)"
        name = "Bubble Sort"
    elif algo == "insertion":
        sorted_arr, elapsed = dsa.insertion_sort(data, key=req.key, reverse=req.reverse)
        complexity = "O(n^2)"
        name = "Insertion Sort"
    elif algo == "merge":
        sorted_arr, elapsed = dsa.merge_sort(data, key=req.key, reverse=req.reverse)
        complexity = "O(n log n)"
        name = "Merge Sort"
    elif algo == "quick":
        sorted_arr, elapsed = dsa.quick_sort(data, key=req.key, reverse=req.reverse)
        complexity = "O(n log n) avg, O(n^2) worst"
        name = "Quick Sort"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported algorithm '{req.algorithm}'.")

    return {
        "algorithm": name,
        "time_complexity": complexity,
        "key": req.key,
        "reverse": req.reverse,
        "time_taken_seconds": round(elapsed, 6),
        "total_items": len(sorted_arr),
        "results": sorted_arr
    }


# ============================================================================
# Member History Linked List
# ============================================================================

@app.get("/api/members/{roll_no}/history")
def get_member_history(roll_no: str, user: dict = Depends(auth.get_current_user_from_header)):
    """Traverses linked list per member to return participation history."""
    clean_roll = roll_no.strip().upper()
    hist_ll = storage.member_histories.get(clean_roll)
    if not hist_ll:
        return {"roll_no": clean_roll, "count": 0, "history": []}
    return {
        "roll_no": clean_roll,
        "count": len(hist_ll),
        "history": hist_ll.traverse()
    }


# ============================================================================
# Event & Form Management Endpoints
# ============================================================================

@app.get("/api/events")
def list_events(user: dict = Depends(auth.get_current_user_from_header)):
    return storage.get_events()


@app.post("/api/events")
def create_event(
    event: EventModel,
    user: dict = Depends(auth.require_role(["admin", "cabinet"]))
):
    if event.start_time and event.end_time:
        try:
            start = datetime.strptime(event.start_time, "%H:%M")
            end = datetime.strptime(event.end_time, "%H:%M")
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Event start_time and end_time must use HH:MM format.",
            ) from exc
        if start >= end:
            raise HTTPException(
                status_code=400,
                detail="Event start time must be before end time.",
            )
    ev_dict = event.dict()
    ev_dict["created_by"] = user.get("username", "admin")
    ok, msg = storage.add_event(ev_dict, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "event": ev_dict}


@app.put("/api/events/{event_id}")
def update_event(
    event_id: str,
    updates: Dict[str, Any],
    user: dict = Depends(auth.require_role(["admin"]))
):
    """Admin only: edits event details."""
    ok, msg = storage.update_event(event_id, updates, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.get("/api/events/{event_id}/participants")
def event_participants(event_id: str, user: dict = Depends(auth.get_current_user_from_header)):
    """Event-wise lists: volunteers, attendees, attendance and assignments for one event."""
    ev = next((e for e in storage.get_events() if e.get("event_id") == event_id), None)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found.")
    form_ids = {f.get("form_id") for f in storage.get_forms() if f.get("event_id") == event_id}
    title = ev.get("title")

    def _for_event(rows):
        return [r for r in rows if r.get("form_id") in form_ids or r.get("event_title") == title]

    return {
        "event": ev,
        "volunteers": _for_event(storage.get_volunteers()),
        "attendees": _for_event(storage.get_attendees()),
        "attendance": [a for a in storage.get_attendance() if a.get("event_id") == event_id],
        "assignments": [a for a in storage.get_assignments() if a.get("event_id") == event_id],
    }


@app.delete("/api/events/{event_id}")
def delete_event(event_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    """Admin only: deletes an event."""
    ok, msg = storage.delete_event(event_id, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.get("/api/forms")
def list_all_forms(user: dict = Depends(auth.get_current_user_from_header)):
    forms = storage.get_forms()
    res = []
    for f in forms:
        f_copy = dict(f)
        is_op, status_text = is_form_open(f)
        f_copy["computed_is_open"] = is_op
        f_copy["status_message"] = status_text
        res.append(f_copy)
    return res


@app.post("/api/forms")
def create_form(form: FormModel, user: dict = Depends(auth.require_role(["admin"]))):
    """Admin only: creates a new Volunteer or Attendee form."""
    form_dict = form.dict()
    ok, msg = storage.add_form(form_dict, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "form": form_dict}


@app.put("/api/forms/{form_id}")
def update_form_settings(
    form_id: str,
    updates: Dict[str, Any],
    user: dict = Depends(auth.require_role(["admin"]))
):
    """Admin only: updates form details or toggles manual open/close state."""
    ok, msg = storage.update_form(form_id, updates, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/admin/migrate-form-description/{form_id}")
def migrate_form_description(
    form_id: str,
    migration: Dict[str, str],
    user: dict = Depends(auth.require_role(["admin"])),
):
    """Admin-only exact migration for one Production Blob workbook cell."""
    required = {"old_description", "new_description"}
    if set(migration) != required:
        raise HTTPException(status_code=400, detail="Invalid description migration request.")
    ok, message = storage.migrate_form_description(
        form_id,
        migration["old_description"],
        migration["new_description"],
    )
    if not ok:
        raise HTTPException(status_code=409, detail=message)
    return {"success": True, "message": message}


@app.delete("/api/forms/{form_id}")
def delete_form(form_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    """Admin only: deletes a form."""
    ok, msg = storage.delete_form(form_id, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# ============================================================================
# Members CRUD
# ============================================================================

@app.get("/api/members")
def list_members(user: dict = Depends(auth.get_current_user_from_header)):
    return storage.get_members()


@app.post("/api/members")
def add_member(member: MemberModel, user: dict = Depends(auth.require_role(["admin"]))):
    ok, msg = storage.add_member(member.dict(), actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.put("/api/members/{member_id}")
def update_member(member_id: str, updates: Dict[str, Any], user: dict = Depends(auth.require_role(["admin"]))):
    ok, msg = storage.update_member(member_id, updates, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.delete("/api/members/{member_id}")
def delete_member(member_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    ok, msg = storage.delete_member(member_id, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# ============================================================================
# Submissions Management (Volunteers & Attendees)
# ============================================================================

@app.get("/api/submissions/volunteers")
def list_volunteers(user: dict = Depends(auth.get_current_user_from_header)):
    return storage.get_volunteers()


@app.get("/api/submissions/attendees")
def list_attendees(user: dict = Depends(auth.get_current_user_from_header)):
    return storage.get_attendees()


@app.get("/api/submissions/registrations")
def list_all_registrations(user: dict = Depends(auth.get_current_user_from_header)):
    return storage.get_registrations()


@app.post("/api/submissions/{submission_id}/review")
def review_submission(
    submission_id: str,
    status: str = Form(...),  # "Approved" or "Rejected"
    user: dict = Depends(auth.get_current_user_from_header)
):
    """Approves or Rejects a registration submission."""
    reviewer = f"{user.get('full_name')} ({user.get('username')})"
    ok, msg = storage.update_submission_status(
        submission_id=submission_id,
        new_status=status,
        reviewed_by=reviewer
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# ============================================================================
# Attendance & Assignments
# ============================================================================

@app.get("/api/attendance")
def list_attendance(user: dict = Depends(auth.get_current_user_from_header)):
    return storage.get_attendance()


@app.post("/api/attendance")
def mark_attendance(
    event_id: str = Form(...),
    roll_no: str = Form(...),
    role: str = Form("Attendee"),
    status: str = Form("Present"),
    user: dict = Depends(auth.get_current_user_from_header)
):
    clean_roll = roll_no.strip().upper()
    events = storage.get_events()
    ev = next((e for e in events if e.get("event_id") == event_id), None)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found.")
    event_title = ev.get("title", "")

    # Fetch candidate name from Members or Submissions
    candidate_name = clean_roll
    mem = storage.members_ll.find_by_id(clean_roll, id_key="roll_no")
    if mem:
        candidate_name = mem.get("name")
    else:
        regs = storage.get_registrations()
        for r in regs:
            if r.get("roll_no", "").strip().upper() == clean_roll:
                candidate_name = r.get("candidate_name")
                break
        if candidate_name == clean_roll:
            raise HTTPException(
                status_code=400,
                detail="Attendance can only be marked for a registered participant.",
            )

    at_id = f"ATN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{clean_roll[-3:]}"
    at_rec = {
        "attendance_id": at_id,
        "event_id": event_id,
        "event_title": event_title,
        "roll_no": clean_roll,
        "candidate_name": candidate_name,
        "role": role,
        "marked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "marked_by": f"{user.get('full_name')} ({user.get('username')})",
        "status": status
    }

    ok, msg = storage.mark_attendance(at_rec, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "record": at_rec}


@app.delete("/api/attendance/{attendance_id}")
def delete_attendance_record(attendance_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    ok, msg = storage.delete_attendance(attendance_id, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.delete("/api/assignments/{assignment_id}")
def delete_assignment_record(assignment_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    ok, msg = storage.delete_assignment(assignment_id, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.get("/api/assignments")
def list_assignments(user: dict = Depends(auth.get_current_user_from_header)):
    return storage.get_assignments()


@app.post("/api/assignments")
def assign_volunteer_task(
    event_id: str = Form(...),
    volunteer_roll_no: str = Form(...),
    task_description: str = Form(...),
    user: dict = Depends(auth.get_current_user_from_header)
):
    clean_roll = volunteer_roll_no.strip().upper()
    events = storage.get_events()
    ev = next((e for e in events if e.get("event_id") == event_id), None)
    event_title = ev.get("title", "") if ev else "Event"

    # Get volunteer name
    name = clean_roll
    vols = storage.get_volunteers()
    for v in vols:
        if v.get("roll_no", "").strip().upper() == clean_roll:
            name = v.get("candidate_name", clean_roll)
            break

    asg_id = f"ASN-{uuid.uuid4().hex[:6].upper()}"
    rec = {
        "assignment_id": asg_id,
        "event_id": event_id,
        "event_title": event_title,
        "volunteer_roll_no": clean_roll,
        "volunteer_name": name,
        "task_description": task_description,
        "assigned_by": f"{user.get('full_name')} ({user.get('username')})",
        "status": "Assigned",
        "assigned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    ok, msg = storage.add_assignment(rec, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg, "assignment": rec}


@app.put("/api/assignments/{assignment_id}/status")
def update_assignment_status(
    assignment_id: str,
    status: str = Form(...),
    user: dict = Depends(auth.get_current_user_from_header)
):
    ok, msg = storage.update_assignment_status(assignment_id, status, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# ============================================================================
# Cabinet Accounts Management (Admin Only)
# ============================================================================

@app.get("/api/admin/cabinet")
def list_cabinet_accounts(user: dict = Depends(auth.require_role(["admin"]))):
    # Hide password hashes and salts in response for clean security
    accs = storage.get_cabinet_accounts()
    safe = []
    for a in accs:
        c = dict(a)
        c.pop("password_hash", None)
        c.pop("salt", None)
        safe.append(c)
    return safe


@app.post("/api/admin/cabinet")
def create_cabinet_account(
    account: CabinetAccountCreate,
    user: dict = Depends(auth.require_role(["admin"]))
):
    pwd_hash, salt = auth.hash_password(account.password)
    rec = {
        "username": account.username.strip().lower(),
        "full_name": account.full_name.strip(),
        "title": account.title.strip(),
        "role": "cabinet",
        "email": account.email.strip() if account.email else "",
        "phone": account.phone.strip() if account.phone else "",
        "status": "Active",
        "password_hash": pwd_hash,
        "salt": salt,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    ok, msg = storage.add_cabinet_account(rec, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.put("/api/admin/cabinet/{username}")
def edit_cabinet_account(
    username: str,
    updates: CabinetAccountUpdate,
    user: dict = Depends(auth.require_role(["admin"]))
):
    up_dict = {k: v for k, v in updates.dict().items() if v is not None}
    if "password" in up_dict and up_dict["password"]:
        p_hash, salt = auth.hash_password(up_dict.pop("password"))
        up_dict["password_hash"] = p_hash
        up_dict["salt"] = salt

    ok, msg = storage.update_cabinet_account(username, up_dict, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@app.post("/api/admin/cabinet/{username}/reset-password")
def reset_cabinet_password(
    username: str,
    new_password: str = Form(...),
    user: dict = Depends(auth.require_role(["admin"]))
):
    ok, msg = storage.reset_password(username, new_password, actor=user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# ============================================================================
# Allowed Roll Numbers (Admin Only)
# ============================================================================

@app.get("/api/admin/allowed-rolls")
def get_allowed_rolls(user: dict = Depends(auth.require_role(["admin"]))):
    rolls = sorted(list(auth.get_allowed_roll_numbers()))
    return {"count": len(rolls), "allowed_roll_numbers": rolls}


@app.post("/api/admin/upload-allowed-rolls")
async def upload_allowed_rolls(
    file: UploadFile = File(...),
    user: dict = Depends(auth.require_role(["admin"]))
):
    """Uploads a CSV to replace or update the allowed roll numbers list."""
    contents = await file.read()
    try:
        decoded = contents.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(decoded))
        new_rolls = []
        for r in reader:
            if r:
                candidate = r[0].strip().upper()
                if candidate and candidate != "ROLL_NO" and auth.valid_roll_no(candidate):
                    new_rolls.append(candidate)

        if not new_rolls:
            raise HTTPException(status_code=400, detail="No valid Data Science roll numbers found in CSV file.")

        auth.save_allowed_roll_numbers(new_rolls)
        storage.log_activity(user.get("username"), "UPLOAD_ALLOWED_ROLLS", f"Updated allowed roll list with {len(new_rolls)} students.")
        return {"success": True, "count": len(new_rolls), "message": f"Allowed roll numbers updated successfully with {len(new_rolls)} entries."}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except HTTPException:
        raise
    except (UnicodeDecodeError, csv.Error, OSError) as e:
        raise HTTPException(status_code=400, detail=f"Could not parse the CSV file: {str(e)}")


# ============================================================================
# Downloads & Audit Logs
# ============================================================================

@app.get("/api/admin/download/records-excel")
def download_records_excel(user: dict = Depends(auth.require_role(["admin", "cabinet"]))):
    """Downloads the records.xlsx file."""
    if not os.path.exists(storage.RECORDS_EXCEL_PATH):
        raise HTTPException(status_code=404, detail="records.xlsx not found.")
    return FileResponse(
        storage.RECORDS_EXCEL_PATH,
        filename="records.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/api/admin/download/id-cards-zip")
def download_id_cards_zip(user: dict = Depends(auth.require_role(["admin"]))):
    """Admin only: downloads all submitted student ID card photos in a ZIP file."""
    zip_buffer = storage.create_id_cards_zip()
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=ddss_id_cards.zip"}
    )


@app.get("/api/admin/download/activity-log")
def download_activity_log(user: dict = Depends(auth.require_role(["admin"]))):
    """Admin only: downloads the raw activity_log.txt file."""
    if not os.path.exists(storage.ACTIVITY_LOG_PATH):
        raise HTTPException(status_code=404, detail="activity_log.txt not found.")
    return FileResponse(
        storage.ACTIVITY_LOG_PATH,
        filename="activity_log.txt",
        media_type="text/plain"
    )


@app.get("/api/admin/download/registrations-csv")
def download_registrations_csv(user: dict = Depends(auth.require_role(["admin", "cabinet"]))):
    """Downloads the current registration report as CSV."""
    rows = storage.get_registrations()
    output = io.StringIO(newline="")
    fieldnames = list(storage.SHEET_SCHEMAS["Registrations"])
    writer = csv.DictWriter(
        output,
        fieldnames=[field.lower().replace(" ", "_").replace("-", "_") for field in fieldnames],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=registrations.csv"},
    )


@app.get("/api/admin/download/backup-json")
def download_backup_json(user: dict = Depends(auth.require_role(["admin"]))):
    """Downloads a JSON backup assembled from the authoritative file stores."""
    backup = {
        "records": {
            "members": storage.get_members(),
            "events": storage.get_events(),
            "forms": storage.get_forms(),
            "registrations": storage.get_registrations(),
            "attendance": storage.get_attendance(),
            "assignments": storage.get_assignments(),
            "cabinet_accounts": storage.get_cabinet_accounts(),
        },
        "allowed_roll_numbers": sorted(auth.get_allowed_roll_numbers()),
        "activity_log": storage.read_activity_log(limit=10000),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }
    return StreamingResponse(
        iter([json.dumps(backup, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=ddss-backup.json"},
    )



@app.get("/api/admin/export/event-excel/{form_id}")
def export_event_excel(form_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    """Exports event data as Excel bytes without clearing (for preparation)."""
    import pandas as pd

    volunteers = storage.get_volunteers()
    attendees = storage.get_attendees()

    event_vols = [v for v in volunteers if v.get("form_id", "").strip().lower() == form_id.strip().lower()]
    event_atts = [a for a in attendees if a.get("form_id", "").strip().lower() == form_id.strip().lower()]
    all_event_data = event_vols + event_atts

    if not all_event_data:
        raise HTTPException(status_code=404, detail="No submissions found for this form/event.")

    event_title = all_event_data[0].get("event_title", "Event") if all_event_data else "Event"

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if event_vols:
            pd.DataFrame(event_vols).to_excel(writer, sheet_name="Volunteers", index=False)
        if event_atts:
            pd.DataFrame(event_atts).to_excel(writer, sheet_name="Attendees", index=False)
        if all_event_data:
            pd.DataFrame(all_event_data).to_excel(writer, sheet_name="All Registrations", index=False)
    output.seek(0)
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', event_title)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={safe_title}_{form_id}.xlsx"}
    )


@app.post("/api/admin/events/{form_id}/clear-data")
def clear_event_data_endpoint(form_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    """Clears all stored data for an event/form."""
    storage.clear_event_data(form_id)
    return {"success": True, "message": f"All stored data for form '{form_id}' has been cleared."}


@app.get("/api/admin/download/event-excel/{form_id}")
def download_event_excel(form_id: str, user: dict = Depends(auth.require_role(["admin"]))):
    """Downloads event data as Excel and clears the stored data for that form/event."""
    import pandas as pd

    # Get all submissions for this form
    volunteers = storage.get_volunteers()
    attendees = storage.get_attendees()

    event_vols = [v for v in volunteers if v.get("form_id", "").strip().lower() == form_id.strip().lower()]
    event_atts = [a for a in attendees if a.get("form_id", "").strip().lower() == form_id.strip().lower()]
    all_event_data = event_vols + event_atts

    if not all_event_data:
        raise HTTPException(status_code=404, detail="No submissions found for this form/event.")

    event_title = all_event_data[0].get("event_title", "Event") if all_event_data else "Event"

    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if event_vols:
            pd.DataFrame(event_vols).to_excel(writer, sheet_name="Volunteers", index=False)
        if event_atts:
            pd.DataFrame(event_atts).to_excel(writer, sheet_name="Attendees", index=False)
        if all_event_data:
            pd.DataFrame(all_event_data).to_excel(writer, sheet_name="All Registrations", index=False)
    output.seek(0)

    # Clear stored data for this event/form after creating the download
    storage.clear_event_data(form_id)
    storage.log_activity(
        user.get("username", "admin"),
        "EVENT_DATA_DOWNLOAD_AND_CLEAR",
        f"Downloaded and cleared all data for form '{form_id}' (Event: {event_title})."
    )

    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', event_title)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={safe_title}_{form_id}.xlsx"}
    )
@app.get("/api/admin/audit-log")
def view_audit_log(limit: int = 150, user: dict = Depends(auth.require_role(["admin"]))):
    """Admin only: returns the last N entries of activity_log.txt."""
    lines = storage.read_activity_log(limit=limit)
    return {"count": len(lines), "logs": lines}
