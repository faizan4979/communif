"""
Storage and Excel Module for DDSS.
Manages records.xlsx using openpyxl with a threading lock,
activity_log.txt auditing, and image uploads.
Synchronizes data with custom DSA structures in backend/dsa.py.
"""

import os
import io
import zipfile
import threading
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from backend.dsa import (
    SinglyLinkedList,
    EventScheduleArray,
    Queue,
    Stack,
    MemberParticipationHistory,
    linear_search,
    binary_search,
    bubble_sort,
    insertion_sort,
    merge_sort,
    quick_sort
)
from backend.auth import hash_password
from backend import blob_storage

# Base Directories
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECORDS_EXCEL_PATH = PROJECT_ROOT / "records.xlsx"
ACTIVITY_LOG_PATH = PROJECT_ROOT / "activity_log.txt"
UPLOADS_DIR = PROJECT_ROOT / "uploads"

# Thread lock for thread-safe Excel read/writes
EXCEL_LOCK = threading.Lock()

# DSA In-Memory Structures
members_ll = SinglyLinkedList()
volunteers_ll = SinglyLinkedList()
attendees_ll = SinglyLinkedList()
schedule_array = EventScheduleArray()
submissions_queue = Queue()
undo_stack = Stack()
member_histories: Dict[str, MemberParticipationHistory] = {}
cabinet_accounts_list: List[Dict[str, Any]] = []
_BLOB_RUNTIME = False
_BLOB_ROOT: Optional[Path] = None

SHEET_SCHEMAS = {
    "Members": [
        "Member ID", "Name", "Roll No", "Phone", "Department", "Email", "Status", "Joined At"
    ],
    "Volunteers": [
        "Submission ID", "Form ID", "Event Title", "Candidate Name", "Roll No",
        "Phone No", "Department", "Email", "University Email", "ID Card File", "Submitted At", "Status", "Reviewed By"
    ],
    "Attendees": [
        "Submission ID", "Form ID", "Event Title", "Candidate Name", "Roll No",
        "Phone No", "Department", "Email", "University Email", "ID Card File", "Submitted At", "Status", "Reviewed By"
    ],
    "Events": [
        "Event ID", "Title", "Description", "Date", "Time", "Start Time",
        "End Time", "Venue", "Status", "Created By", "Created At"
    ],
    "Forms": [
        "Form ID", "Event ID", "Event Title", "Form Type", "Description",
        "Is Open Manual", "Open Time", "Close Time", "Max Seats", "Created At"
    ],
    "Registrations": [
        "Registration ID", "Form ID", "Form Type", "Event Title", "Candidate Name",
        "Roll No", "Phone No", "Department", "Email", "University Email", "ID Card File", "Submitted At",
        "Status", "Reviewed By"
    ],
    "Attendance": [
        "Attendance ID", "Event ID", "Event Title", "Roll No", "Candidate Name",
        "Role", "Marked At", "Marked By", "Status"
    ],
    "Assignments": [
        "Assignment ID", "Event ID", "Event Title", "Volunteer Roll No", "Volunteer Name",
        "Task Description", "Assigned By", "Status", "Assigned At"
    ],
    "Cabinet": [
        "Username", "Full Name", "Title", "Role", "Email", "Phone",
        "Status", "Password Hash", "Salt", "Created At"
    ],
    "Queue": [
        "Submission ID", "Form ID", "Form Type", "Event Title", "Candidate Name",
        "Roll No", "Submitted At", "Status"
    ],
    "Participation History": [
        "Roll No", "Candidate Name", "Event ID", "Event Title", "Role",
        "Attendance Status", "Marked At", "Marked By"
    ]
}


def log_activity(actor: str, action: str, details: str) -> None:
    """
    Appends one line to activity_log.txt.
    Format: 2026-10-24 11:15:03 | 25F-DS-052 | SUBMIT_VOLUNTEER_FORM | Form F01 submitted.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{now_str} | {actor.strip()} | {action.strip()} | {details.strip()}\n"
    if is_vercel_runtime() and not _BLOB_RUNTIME:
        print(f"[Activity log unavailable] {line.rstrip()}")
        return
    try:
        with open(ACTIVITY_LOG_PATH, mode="a", encoding="utf-8") as f:
            f.write(line)
        if _BLOB_RUNTIME:
            _ensure_blob_seeded()
            blob_storage.write("activity_log.txt", ACTIVITY_LOG_PATH.read_bytes(), "text/plain")
    except Exception as e:
        print(f"[Error writing activity log]: {e}")


def read_activity_log(limit: int = 100) -> List[str]:
    """Reads the last N lines of activity_log.txt."""
    if not os.path.exists(ACTIVITY_LOG_PATH):
        return []
    try:
        with open(ACTIVITY_LOG_PATH, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
        return [l.strip() for l in lines[-limit:]]
    except Exception:
        return []


def _apply_sheet_styling(ws, headers: List[str]) -> None:
    """Applies clean DUET Navy & White styling to header row."""
    header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='D0D7DE'),
        right=Side(style='thin', color='D0D7DE'),
        top=Side(style='thin', color='D0D7DE'),
        bottom=Side(style='thin', color='D0D7DE')
    )

    for col_idx, h_text in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h_text)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = max(len(h_text) + 6, 16)
    ws.row_dimensions[1].height = 26


def _row_to_dict(headers: List[str], row_values: tuple) -> Dict[str, Any]:
    """Converts a row tuple to a dictionary mapped by slugified or lowercase keys."""
    d = {}
    for h, v in zip(headers, row_values):
        key = h.lower().replace(" ", "_").replace("-", "_")
        d[key] = "" if v is None else str(v).strip()
    return d


def is_vercel_runtime() -> bool:
    """Returns whether the process is running in Vercel's serverless runtime."""
    return os.getenv("VERCEL", "").strip().lower() in {"1", "true", "yes"}


def init_storage(read_only: Optional[bool] = None) -> None:
    """
    Initializes storage and populates the in-memory DSA structures.

    Vercel uses read-only initialization because its deployed repository files
    must not be rewritten while importing the FastAPI application.
    """
    global _BLOB_RUNTIME, _BLOB_ROOT, RECORDS_EXCEL_PATH, ACTIVITY_LOG_PATH, UPLOADS_DIR
    if read_only is None:
        read_only = is_vercel_runtime()

    _BLOB_RUNTIME = bool(read_only and is_vercel_runtime())
    if _BLOB_RUNTIME:
        _BLOB_ROOT = Path(tempfile.mkdtemp(prefix="ddss-blob-"))
        RECORDS_EXCEL_PATH = _BLOB_ROOT / "records.xlsx"
        ACTIVITY_LOG_PATH = _BLOB_ROOT / "activity_log.txt"
        UPLOADS_DIR = _BLOB_ROOT / "uploads"
        _load_blob_file("records.xlsx", RECORDS_EXCEL_PATH)
        _load_blob_file("activity_log.txt", ACTIVITY_LOG_PATH)

    if not read_only:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        if not RECORDS_EXCEL_PATH.exists():
            _create_default_workbook()
        else:
            _ensure_workbook_structure()

    # Load into DSA structures
    load_all_records_to_dsa()


def _load_blob_file(pathname: str, destination: Path) -> None:
    try:
        contents = blob_storage.read(pathname)
    except blob_storage.BlobStorageError:
        contents = None
    if contents is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contents)
    else:
        source = PROJECT_ROOT / pathname
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())


def _ensure_blob_seeded() -> None:
    if not _BLOB_RUNTIME:
        raise OSError(
            "Persistent file storage is unavailable on the backend."
        )
    if blob_storage.read("records.xlsx") is None:
        blob_storage.write("records.xlsx", Path(PROJECT_ROOT / "records.xlsx").read_bytes(),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if blob_storage.read("allowed_roll_numbers.csv") is None:
        blob_storage.write("allowed_roll_numbers.csv", (PROJECT_ROOT / "allowed_roll_numbers.csv").read_bytes(),
                           "text/csv")
    if blob_storage.read("activity_log.txt") is None:
        blob_storage.write("activity_log.txt", (PROJECT_ROOT / "activity_log.txt").read_bytes(),
                           "text/plain")


def _persist_blob_workbook() -> None:
    if _BLOB_RUNTIME:
        _ensure_blob_seeded()
        blob_storage.write(
            "records.xlsx",
            RECORDS_EXCEL_PATH.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _refresh_blob_workbook() -> None:
    """Refreshes the production read snapshot from the current Blob object."""
    if not _BLOB_RUNTIME:
        return
    try:
        contents = blob_storage.read("records.xlsx")
    except blob_storage.BlobStorageError:
        return
    if contents is not None:
        RECORDS_EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECORDS_EXCEL_PATH.write_bytes(contents)


def _ensure_workbook_structure() -> None:
    """Adds required sheets/columns without removing existing workbook data."""
    with EXCEL_LOCK:
        wb = load_workbook(RECORDS_EXCEL_PATH)
        changed = False
        for sheet_name, headers in SHEET_SCHEMAS.items():
            if sheet_name not in wb.sheetnames:
                _apply_sheet_styling(wb.create_sheet(title=sheet_name), headers)
                changed = True
                continue
            ws = wb[sheet_name]
            existing = [
                str(cell.value).strip() if cell.value is not None else ""
                for cell in ws[1]
            ] if ws.max_row else []
            missing = [header for header in headers if header not in existing]
            if missing:
                for header in missing:
                    ws.cell(row=1, column=ws.max_column + 1, value=header)
                _apply_sheet_styling(ws, headers)
                changed = True

        _refresh_derived_sheets(wb)
        changed = True
        if changed:
            wb.save(RECORDS_EXCEL_PATH)


def _create_default_workbook() -> None:
    """Creates initial records.xlsx with full sample data."""
    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    # 1. Sheet Creation
    for sheet_name, headers in SHEET_SCHEMAS.items():
        ws = wb.create_sheet(title=sheet_name)
        _apply_sheet_styling(ws, headers)

    # 2. Add Default 10 Accounts (1 admin + 9 cabinet)
    default_accounts = [
        ("admin", "System Administrator", "Lead Administrator", "admin", "admin@duet.edu.pk", "03001112233", "Active", "AdminPassword@123"),
        ("president", "Syed Muhammad Ali", "President", "cabinet", "ali.president@duet.edu.pk", "03001234561", "Active", "President@123"),
        ("vp", "Fatima Noor", "Vice President", "cabinet", "fatima.vp@duet.edu.pk", "03001234562", "Active", "VicePres@123"),
        ("gensec", "Hamza Tariq", "General Secretary", "cabinet", "hamza.sec@duet.edu.pk", "03001234563", "Active", "GenSec@123"),
        ("treasurer", "Ayesha Siddiqua", "Treasurer", "cabinet", "ayesha.treasurer@duet.edu.pk", "03001234564", "Active", "Treasurer@123"),
        ("eventmgr", "Bilal Ahmed Khan", "Event Manager", "cabinet", "bilal.event@duet.edu.pk", "03001234565", "Active", "EventMgr@123"),
        ("mediahead", "Zainab Raza", "Media Head", "cabinet", "zainab.media@duet.edu.pk", "03001234566", "Active", "MediaHead@123"),
        ("techhead", "Usman Farooq", "Technical Head", "cabinet", "usman.tech@duet.edu.pk", "03001234567", "Active", "TechHead@123"),
        ("mktghead", "Hafsa Rehman", "Marketing Head", "cabinet", "hafsa.mktg@duet.edu.pk", "03001234568", "Active", "MktgHead@123"),
        ("dischead", "Mustafa Qureshi", "Discipline Head", "cabinet", "mustafa.disc@duet.edu.pk", "03001234569", "Active", "DiscHead@123")
    ]

    ws_cabinet = wb["Cabinet"]
    for acc in default_accounts:
        pwd_hash, salt = hash_password(acc[7])
        ws_cabinet.append([
            acc[0], acc[1], acc[2], acc[3], acc[4], acc[5], acc[6], pwd_hash, salt, "2026-10-01 00:00:00"
        ])

    # 3. Add 10 Sample Members
    sample_members = [
        ("MEM-001", "Muhammad Ahmed", "25F-DS-001", "03009988771", "Data Science", "ahmed@duet.edu.pk", "Active", "2026-09-01"),
        ("MEM-002", "Sana Javed", "25F-DS-002", "03009988772", "Data Science", "sana@duet.edu.pk", "Active", "2026-09-02"),
        ("MEM-003", "Ali Raza", "25F-DS-003", "03009988773", "Data Science", "raza@duet.edu.pk", "Active", "2026-09-03"),
        ("MEM-004", "Hira Khan", "25F-DS-004", "03009988774", "Data Science", "hira@duet.edu.pk", "Active", "2026-09-04"),
        ("MEM-005", "Zubair Siddiqui", "25F-DS-005", "03009988775", "Data Science", "zubair@duet.edu.pk", "Active", "2026-09-05"),
        ("MEM-006", "Mahnoor Aslam", "25F-DS-006", "03009988776", "Data Science", "mahnoor@duet.edu.pk", "Active", "2026-09-06"),
        ("MEM-007", "Taha Sheikh", "25F-DS-007", "03009988777", "Data Science", "taha@duet.edu.pk", "Active", "2026-09-07"),
        ("MEM-008", "Kinza Fatima", "25F-DS-008", "03009988778", "Data Science", "kinza@duet.edu.pk", "Active", "2026-09-08"),
        ("MEM-009", "Osama Bashir", "25F-DS-009", "03009988779", "Data Science", "osama@duet.edu.pk", "Active", "2026-09-09"),
        ("MEM-010", "Iqra Munir", "25F-DS-010", "03009988710", "Data Science", "iqra@duet.edu.pk", "Active", "2026-09-10")
    ]
    ws_members = wb["Members"]
    for m in sample_members:
        ws_members.append(list(m))

    # 4. Add 5 Sample Events
    sample_events = [
        ("EVT-001", "Data Science Bootcamp 2026", "Intensive hands-on Python & ML workshop for freshman undergraduates", "2026-11-05", "10:00", "10:00", "16:00", "Main Auditorium", "Upcoming", "admin", "2026-10-01 09:00:00"),
        ("EVT-002", "DUET AI & Data Summit", "Annual keynote conference featuring industry leaders and tech stalls", "2026-11-15", "09:30", "09:30", "17:00", "DUET Convocation Hall", "Upcoming", "admin", "2026-10-01 09:05:00"),
        ("EVT-003", "Kaggle Hackathon Spring", "24-hour predictive modeling competition with cash prizes", "2026-11-20", "14:00", "14:00", "23:59", "DS Computer Lab 1", "Upcoming", "president", "2026-10-01 09:10:00"),
        ("EVT-004", "Industry Career & Resume Clinic", "Guidance session by DUET alumni working in Top Data firms", "2026-11-28", "11:00", "11:00", "14:00", "Seminar Hall B", "Upcoming", "vp", "2026-10-01 09:15:00"),
        ("EVT-005", "Data Visualization Masterclass", "Tableau and PowerBI dashboard workshop", "2026-10-15", "15:00", "15:00", "18:00", "DS Lab 2", "Completed", "techhead", "2026-10-01 09:20:00")
    ]
    ws_events = wb["Events"]
    for ev in sample_events:
        ws_events.append(list(ev))

    # 5. Add 3 Forms (2 open, 1 closed)
    sample_forms = [
        ("FORM-001", "EVT-001", "Data Science Bootcamp 2026", "Volunteer", "Join the event organizing team as a volunteer guide, usher, or lab mentor.", "True", "2026-10-01 00:00:00", "2026-11-04 23:59:59", "30", "2026-10-01 10:00:00"),
        ("FORM-002", "EVT-002", "DUET AI & Data Summit", "Attendee", "Register your attendee seat for keynotes, workshops, and high tea.", "True", "2026-10-01 00:00:00", "2026-11-14 23:59:59", "200", "2026-10-01 10:30:00"),
        ("FORM-003", "EVT-005", "Data Visualization Masterclass", "Attendee", "Registration is now concluded for the completed masterclass.", "False", "2026-10-01 00:00:00", "2026-10-14 23:59:59", "50", "2026-10-01 11:00:00")
    ]
    ws_forms = wb["Forms"]
    for f in sample_forms:
        ws_forms.append(list(f))

    # Create dummy ID card placeholder in uploads
    dummy_pic = UPLOADS_DIR / "sample_idcard.png"
    if not dummy_pic.exists():
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (400, 250), color=(26, 54, 93))
            d = ImageDraw.Draw(img)
            d.text((40, 110), "DUET STUDENT ID CARD", fill=(255, 255, 255))
            img.save(str(dummy_pic), "PNG")
        except Exception:
            pass

    # 6. Add 5 Sample Volunteers
    sample_volunteers = [
        ("VOL-001", "FORM-001", "Data Science Bootcamp 2026", "Muhammad Ahmed", "25F-DS-001", "03009988771", "Data Science", "sample_idcard.png", "2026-10-20 10:15:00", "Approved", "president"),
        ("VOL-002", "FORM-001", "Data Science Bootcamp 2026", "Sana Javed", "25F-DS-002", "03009988772", "Data Science", "sample_idcard.png", "2026-10-21 11:20:00", "Approved", "eventmgr"),
        ("VOL-003", "FORM-001", "Data Science Bootcamp 2026", "Ali Raza", "25F-DS-003", "03009988773", "Data Science", "sample_idcard.png", "2026-10-22 14:05:00", "Pending", "Unassigned"),
        ("VOL-004", "FORM-001", "Data Science Bootcamp 2026", "Hira Khan", "25F-DS-004", "03009988774", "Data Science", "sample_idcard.png", "2026-10-23 09:30:00", "Pending", "Unassigned"),
        ("VOL-005", "FORM-001", "Data Science Bootcamp 2026", "Zubair Siddiqui", "25F-DS-005", "03009988775", "Data Science", "sample_idcard.png", "2026-10-23 16:45:00", "Rejected", "dischead")
    ]
    ws_vol = wb["Volunteers"]
    for v in sample_volunteers:
        ws_vol.append(list(v))

    # 7. Add Sample Attendees
    sample_attendees = [
        ("ATT-001", "FORM-002", "DUET AI & Data Summit", "Mahnoor Aslam", "25F-DS-006", "03009988776", "Data Science", "sample_idcard.png", "2026-10-21 15:30:00", "Approved", "vp"),
        ("ATT-002", "FORM-002", "DUET AI & Data Summit", "Taha Sheikh", "25F-DS-007", "03009988777", "Data Science", "sample_idcard.png", "2026-10-22 16:00:00", "Pending", "Unassigned")
    ]
    ws_att = wb["Attendees"]
    for a in sample_attendees:
        ws_att.append(list(a))

    # 8. Registrations sheet (combined view)
    ws_reg = wb["Registrations"]
    for v in sample_volunteers:
        ws_reg.append([v[0], v[1], "Volunteer", v[2], v[3], v[4], v[5], v[6], v[8], v[9], v[10]])
    for a in sample_attendees:
        ws_reg.append([a[0], a[1], "Attendee", a[2], a[3], a[4], a[5], a[6], a[8], a[9], a[10]])

    # 9. Attendance sheet
    ws_attendance = wb["Attendance"]
    sample_attendance = [
        ("ATN-001", "EVT-005", "Data Visualization Masterclass", "25F-DS-001", "Muhammad Ahmed", "Attendee", "2026-10-15 15:10:00", "techhead", "Present"),
        ("ATN-002", "EVT-005", "Data Visualization Masterclass", "25F-DS-002", "Sana Javed", "Attendee", "2026-10-15 15:15:00", "techhead", "Present")
    ]
    for at in sample_attendance:
        ws_attendance.append(list(at))

    # 10. Assignments sheet
    ws_assign = wb["Assignments"]
    sample_assignments = [
        ("ASN-001", "EVT-001", "Data Science Bootcamp 2026", "25F-DS-001", "Muhammad Ahmed", "Registration desk & badge distribution", "eventmgr", "Assigned", "2026-10-22 10:00:00"),
        ("ASN-002", "EVT-001", "Data Science Bootcamp 2026", "25F-DS-002", "Sana Javed", "Stage handling and speaker escort", "eventmgr", "In Progress", "2026-10-22 10:30:00")
    ]
    for asg in sample_assignments:
        ws_assign.append(list(asg))

    with EXCEL_LOCK:
        wb.save(RECORDS_EXCEL_PATH)

    log_activity("SYSTEM", "INITIALIZE_DATABASE", "Created records.xlsx with default sample data and schemas.")


def _read_sheet_dicts(sheet_name: str) -> List[Dict[str, Any]]:
    """Thread-safe read of a sheet into a list of row dictionaries."""
    _refresh_blob_workbook()
    with EXCEL_LOCK:
        try:
            wb = load_workbook(RECORDS_EXCEL_PATH, data_only=True)
            if sheet_name not in wb.sheetnames:
                return []
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows or len(rows) < 2:
                return []
            headers = [str(h) for h in rows[0]]
            records = []
            for r in rows[1:]:
                if any(v is not None and str(v).strip() != "" for v in r):
                    records.append(_row_to_dict(headers, r))
            return records
        except Exception as e:
            print(f"[Error reading sheet {sheet_name}]: {e}")
            return []


def _write_sheet_dicts(sheet_name: str, records: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Thread-safe overwrite of a sheet's rows using provided dictionaries.
    Handles file locked errors gracefully.
    """
    if is_vercel_runtime() and not _BLOB_RUNTIME:
        return (
            False,
            "Submission could not be saved because persistent file storage is temporarily unavailable. "
            "Please try again later.",
        )
    with EXCEL_LOCK:
        try:
            wb = load_workbook(RECORDS_EXCEL_PATH)
            if sheet_name not in wb.sheetnames:
                ws = wb.create_sheet(title=sheet_name)
            else:
                ws = wb[sheet_name]
                # clear existing rows
                ws.delete_rows(1, ws.max_row + 1)

            headers = SHEET_SCHEMAS.get(sheet_name, [])
            _apply_sheet_styling(ws, headers)

            for rec in records:
                row_val = []
                for h in headers:
                    k = h.lower().replace(" ", "_").replace("-", "_")
                    row_val.append(rec.get(k, ""))
                ws.append(row_val)

            _refresh_derived_sheets(wb)
            wb.save(RECORDS_EXCEL_PATH)
            _persist_blob_workbook()
            return True, "Saved successfully."
        except PermissionError:
            err = "Permission Error: records.xlsx is open or locked by another program. Please close Excel and try again."
            log_activity("SYSTEM", "EXCEL_FILE_LOCKED", err)
            return False, err
        except Exception as e:
            err = f"Failed to save records.xlsx: {str(e)}"
            log_activity("SYSTEM", "EXCEL_WRITE_ERROR", err)
            return False, err


def _refresh_derived_sheets(wb) -> None:
    """Refreshes queue/history reports from the authoritative workbook sheets."""
    queue_records = []
    for source in ("Volunteers", "Attendees"):
        ws = wb[source] if source in wb.sheetnames else None
        if not ws or ws.max_row < 2:
            continue
        rows = list(ws.iter_rows(values_only=True))
        headers = [str(value) for value in rows[0]]
        for row in rows[1:]:
            record = _row_to_dict(headers, row)
            if record.get("status", "").lower() == "pending":
                queue_records.append(record)
    queue_records.sort(key=lambda record: record.get("submitted_at", ""))

    history_records = []
    ws = wb["Attendance"] if "Attendance" in wb.sheetnames else None
    if ws and ws.max_row >= 2:
        rows = list(ws.iter_rows(values_only=True))
        headers = [str(value) for value in rows[0]]
        for row in rows[1:]:
            attendance = _row_to_dict(headers, row)
            history_records.append({
                "roll_no": attendance.get("roll_no", ""),
                "candidate_name": attendance.get("candidate_name", ""),
                "event_id": attendance.get("event_id", ""),
                "event_title": attendance.get("event_title", ""),
                "role": attendance.get("role", ""),
                "attendance_status": attendance.get("status", ""),
                "marked_at": attendance.get("marked_at", ""),
                "marked_by": attendance.get("marked_by", ""),
            })

    for sheet_name, records in (
        ("Queue", queue_records),
        ("Participation History", history_records),
    ):
        if sheet_name not in wb.sheetnames:
            ws = wb.create_sheet(title=sheet_name)
        else:
            ws = wb[sheet_name]
        ws.delete_rows(1, ws.max_row + 1)
        headers = SHEET_SCHEMAS[sheet_name]
        _apply_sheet_styling(ws, headers)
        for record in records:
            ws.append([
                record.get(header.lower().replace(" ", "_").replace("-", "_"), "")
                for header in headers
            ])


def load_all_records_to_dsa() -> None:
    """Populates all in-memory DSA structures from records.xlsx."""
    global cabinet_accounts_list

    # 1. Members -> SinglyLinkedList
    members_ll.clear()
    raw_members = _read_sheet_dicts("Members")
    for m in raw_members:
        members_ll.insert_at_end(m)

    # 2. Volunteers -> SinglyLinkedList
    volunteers_ll.clear()
    raw_volunteers = _read_sheet_dicts("Volunteers")
    for v in raw_volunteers:
        volunteers_ll.insert_at_end(v)

    # 3. Attendees -> SinglyLinkedList
    attendees_ll.clear()
    raw_attendees = _read_sheet_dicts("Attendees")
    for a in raw_attendees:
        attendees_ll.insert_at_end(a)

    # 4. Events & Forms -> EventScheduleArray (sorted by date)
    raw_events = _read_sheet_dicts("Events")
    schedule_array.set_all(raw_events, date_key="date")

    # 5. Pending Submissions -> Queue (FIFO)
    while not submissions_queue.is_empty():
        submissions_queue.dequeue()

    all_submissions = raw_volunteers + raw_attendees
    # Queue preserves arrival order (submitted_at)
    all_submissions.sort(key=lambda x: str(x.get("submitted_at", "")))
    for s in all_submissions:
        if s.get("status", "").lower() == "pending":
            submissions_queue.enqueue(s)

    # 6. Cabinet accounts
    cabinet_accounts_list = _read_sheet_dicts("Cabinet")

    # 7. Member Participation Histories
    member_histories.clear()
    raw_attendance = _read_sheet_dicts("Attendance")
    for at in raw_attendance:
        roll = at.get("roll_no", "").strip().upper()
        if roll:
            if roll not in member_histories:
                member_histories[roll] = MemberParticipationHistory(roll)
            member_histories[roll].add_event(at)


# ============================================================================
# Synchronized CRUD and DSA Operations
# ============================================================================

def get_members() -> List[Dict[str, Any]]:
    return members_ll.traverse()


def get_volunteers() -> List[Dict[str, Any]]:
    return volunteers_ll.traverse()


def get_attendees() -> List[Dict[str, Any]]:
    return attendees_ll.traverse()


def get_events() -> List[Dict[str, Any]]:
    return schedule_array.get_all()


def get_forms() -> List[Dict[str, Any]]:
    return _read_sheet_dicts("Forms")


def get_registrations() -> List[Dict[str, Any]]:
    return _read_sheet_dicts("Registrations")


def get_attendance() -> List[Dict[str, Any]]:
    return _read_sheet_dicts("Attendance")


def get_assignments() -> List[Dict[str, Any]]:
    return _read_sheet_dicts("Assignments")


def get_cabinet_accounts() -> List[Dict[str, Any]]:
    return list(cabinet_accounts_list)


# --- Add / Edit / Delete with Stack Undo Recording ---

def add_member(member: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    """Adds a member to LinkedList, Excel, and pushes inverse action to undo_stack."""
    existing = members_ll.find_by_id(member.get("member_id", ""), id_key="member_id")
    if existing:
        return False, f"Member with ID {member.get('member_id')} already exists."

    members_ll.insert_at_end(member)
    records = members_ll.traverse()
    ok, msg = _write_sheet_dicts("Members", records)
    if not ok:
        members_ll.delete_by_id(member.get("member_id", ""), id_key="member_id")
        return False, msg

    undo_stack.push({
        "type": "DELETE_MEMBER",
        "member_id": member.get("member_id"),
        "description": f"Undo add member {member.get('name')} ({member.get('member_id')})"
    })
    log_activity(actor, "ADD_MEMBER", f"Added member {member.get('name')} ({member.get('roll_no')})")
    return True, "Member added successfully."


def update_member(member_id: str, new_data: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    """Updates member in LinkedList and Excel, and records undo state."""
    old_record = members_ll.find_by_id(member_id, id_key="member_id")
    if not old_record:
        return False, f"Member {member_id} not found."

    old_record_copy = dict(old_record)
    members_ll.update(member_id, new_data, id_key="member_id")
    records = members_ll.traverse()
    ok, msg = _write_sheet_dicts("Members", records)
    if not ok:
        members_ll.update(member_id, old_record_copy, id_key="member_id")
        return False, msg

    undo_stack.push({
        "type": "RESTORE_MEMBER",
        "member_id": member_id,
        "previous_data": old_record_copy,
        "description": f"Undo update member {member_id}"
    })
    log_activity(actor, "UPDATE_MEMBER", f"Updated member {member_id}")
    return True, "Member updated successfully."


def delete_member(member_id: str, actor: str = "admin") -> Tuple[bool, str]:
    """Deletes member from LinkedList and Excel, and records undo state."""
    old_record = members_ll.find_by_id(member_id, id_key="member_id")
    if not old_record:
        return False, f"Member {member_id} not found."

    old_record_copy = dict(old_record)
    members_ll.delete_by_id(member_id, id_key="member_id")
    records = members_ll.traverse()
    ok, msg = _write_sheet_dicts("Members", records)
    if not ok:
        members_ll.insert_at_end(old_record_copy)
        return False, msg

    undo_stack.push({
        "type": "INSERT_MEMBER",
        "data": old_record_copy,
        "description": f"Undo delete member {member_id}"
    })
    log_activity(actor, "DELETE_MEMBER", f"Deleted member {member_id}")
    return True, "Member deleted successfully."


# --- Event Management ---

def add_event(event: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    """Adds event to sorted array and Excel."""
    schedule_array.append(event, date_key="date")
    events = schedule_array.get_all()
    ok, msg = _write_sheet_dicts("Events", events)
    if not ok:
        return False, msg

    undo_stack.push({
        "type": "DELETE_EVENT",
        "event_id": event.get("event_id"),
        "description": f"Undo add event {event.get('title')}"
    })
    log_activity(actor, "ADD_EVENT", f"Created event {event.get('title')} ({event.get('date')})")
    return True, "Event added successfully."


def delete_event(event_id: str, actor: str = "admin") -> Tuple[bool, str]:
    """Deletes event from array and Excel."""
    events = schedule_array.get_all()
    target = None
    new_events = []
    for ev in events:
        if ev.get("event_id", "").strip().lower() == event_id.strip().lower():
            target = ev
        else:
            new_events.append(ev)

    if not target:
        return False, f"Event {event_id} not found."

    schedule_array.set_all(new_events, date_key="date")
    ok, msg = _write_sheet_dicts("Events", new_events)
    if not ok:
        schedule_array.set_all(events, date_key="date")
        return False, msg

    undo_stack.push({
        "type": "RESTORE_EVENT",
        "data": target,
        "description": f"Undo delete event {event_id}"
    })
    log_activity(actor, "DELETE_EVENT", f"Deleted event {event_id}")
    return True, "Event deleted successfully."


def update_event(event_id: str, updates: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    """Updates an event in the sorted array and Excel, and records undo state."""
    events = schedule_array.get_all()
    old = None
    new_events = []
    for ev in events:
        if ev.get("event_id", "").strip().lower() == event_id.strip().lower():
            old = dict(ev)
            merged = dict(ev)
            merged.update({k: v for k, v in updates.items() if k != "event_id"})
            new_events.append(merged)
        else:
            new_events.append(ev)

    if old is None:
        return False, f"Event {event_id} not found."

    schedule_array.set_all(new_events, date_key="date")
    ok, msg = _write_sheet_dicts("Events", schedule_array.get_all())
    if not ok:
        schedule_array.set_all(events, date_key="date")
        return False, msg

    undo_stack.push({
        "type": "REPLACE_EVENT",
        "event_id": old.get("event_id"),
        "previous_data": old,
        "description": f"Undo update event {event_id}"
    })
    log_activity(actor, "UPDATE_EVENT", f"Updated event {event_id}")
    return True, "Event updated successfully."


# --- Form Management ---

def add_form(form_data: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    forms = get_forms()
    for f in forms:
        if f.get("form_id") == form_data.get("form_id"):
            return False, f"Form {form_data.get('form_id')} already exists."

    forms.append(form_data)
    ok, msg = _write_sheet_dicts("Forms", forms)
    if not ok:
        return False, msg

    undo_stack.push({
        "type": "DELETE_FORM",
        "form_id": form_data.get("form_id"),
        "description": f"Undo add form {form_data.get('form_id')}"
    })
    log_activity(actor, "ADD_FORM", f"Created {form_data.get('form_type')} form {form_data.get('form_id')} for {form_data.get('event_title')}")
    return True, "Form created successfully."


def update_form(form_id: str, new_data: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    forms = get_forms()
    old_f = None
    idx = -1
    for i, f in enumerate(forms):
        if f.get("form_id", "").strip().lower() == form_id.strip().lower():
            old_f = dict(f)
            idx = i
            break

    if idx == -1:
        return False, f"Form {form_id} not found."

    forms[idx].update(new_data)
    ok, msg = _write_sheet_dicts("Forms", forms)
    if not ok:
        return False, msg

    undo_stack.push({
        "type": "RESTORE_FORM",
        "form_id": form_id,
        "previous_data": old_f,
        "description": f"Undo update form {form_id}"
    })
    log_activity(actor, "UPDATE_FORM", f"Updated form {form_id}")
    return True, "Form updated successfully."


def migrate_form_description(
    form_id: str,
    old_description: str,
    new_description: str,
) -> Tuple[bool, str]:
    """Updates one Blob-backed Forms description without using the local baseline."""
    if not _BLOB_RUNTIME:
        return False, "Production Blob storage is not active."

    contents = blob_storage.read("records.xlsx")
    if contents is None:
        return False, "Production records workbook was not found."

    workbook = load_workbook(io.BytesIO(contents))
    if "Forms" not in workbook.sheetnames:
        return False, "Production records workbook has no Forms sheet."

    worksheet = workbook["Forms"]
    headers = {
        str(cell.value).strip(): cell.column
        for cell in worksheet[1]
        if cell.value is not None
    }
    form_id_column = headers.get("Form ID")
    description_column = headers.get("Description")
    if not form_id_column or not description_column:
        return False, "Production Forms sheet is missing required columns."

    target_cell = None
    for row in worksheet.iter_rows(min_row=2):
        if str(row[form_id_column - 1].value or "").strip() == form_id:
            target_cell = row[description_column - 1]
            break
    if target_cell is None:
        return False, f"Production form {form_id} was not found."
    if target_cell.value == new_description:
        return True, "Production form description is already up to date."
    if target_cell.value != old_description:
        return False, "Production form description did not match the expected source text."

    target_cell.value = new_description
    updated = io.BytesIO()
    workbook.save(updated)
    updated_bytes = updated.getvalue()
    load_workbook(io.BytesIO(updated_bytes)).close()
    blob_storage.write(
        "records.xlsx",
        updated_bytes,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    return True, "Production form description updated."


def delete_form(form_id: str, actor: str = "admin") -> Tuple[bool, str]:
    forms = get_forms()
    target = None
    remaining = []
    for f in forms:
        if f.get("form_id", "").strip().lower() == form_id.strip().lower():
            target = f
        else:
            remaining.append(f)

    if not target:
        return False, f"Form {form_id} not found."

    ok, msg = _write_sheet_dicts("Forms", remaining)
    if not ok:
        return False, msg

    undo_stack.push({
        "type": "RESTORE_FORM_ROW",
        "data": target,
        "description": f"Undo delete form {form_id}"
    })
    log_activity(actor, "DELETE_FORM", f"Deleted form {form_id}")
    return True, "Form deleted successfully."


# --- Submission Management (Volunteers & Attendees) ---

def add_submission(submission: Dict[str, Any], form_type: str) -> Tuple[bool, str]:
    """
    Adds submission to Volunteer or Attendee sheet, Registrations sheet,
    and enqueues it to submissions_queue.
    """
    target_sheet = "Volunteers" if form_type.lower() == "volunteer" else "Attendees"
    ll_target = volunteers_ll if form_type.lower() == "volunteer" else attendees_ll

    ll_target.insert_at_end(submission)
    records = ll_target.traverse()
    ok, msg = _write_sheet_dicts(target_sheet, records)
    if not ok:
        ll_target.delete_by_id(submission.get("submission_id", ""), id_key="submission_id")
        return False, msg

    # Also update Registrations sheet
    regs = get_registrations()
    regs.append({
        "registration_id": submission.get("submission_id"),
        "form_id": submission.get("form_id"),
        "form_type": form_type,
        "event_title": submission.get("event_title"),
        "candidate_name": submission.get("candidate_name"),
        "roll_no": submission.get("roll_no"),
        "phone_no": submission.get("phone_no"),
        "department": submission.get("department"),
        "id_card_file": submission.get("id_card_file"),
        "submitted_at": submission.get("submitted_at"),
        "status": submission.get("status", "Pending"),
        "reviewed_by": submission.get("reviewed_by", "Unassigned")
    })
    regs_ok, regs_msg = _write_sheet_dicts("Registrations", regs)
    if not regs_ok:
        # Keep the in-memory and workbook submission sheets consistent.
        ll_target.delete_by_id(submission.get("submission_id", ""), id_key="submission_id")
        _write_sheet_dicts(target_sheet, ll_target.traverse())
        return False, regs_msg

    # Enqueue to FIFO queue
    submissions_queue.enqueue(submission)

    log_activity(
        submission.get("roll_no", "ANONYMOUS"),
        f"SUBMIT_{form_type.upper()}_FORM",
        f"Form {submission.get('form_id')} submitted with Ref: {submission.get('submission_id')}"
    )
    return True, "Submission recorded successfully."


def update_submission_status(
    submission_id: str,
    new_status: str,
    reviewed_by: str,
    is_volunteer: bool = True
) -> Tuple[bool, str]:
    """Approves or rejects a submission, pops/removes from Queue, updates Excel."""
    ll_target = volunteers_ll if is_volunteer else attendees_ll
    sheet_name = "Volunteers" if is_volunteer else "Attendees"

    item = ll_target.find_by_id(submission_id, id_key="submission_id")
    if not item:
        # Check the other list just in case
        ll_alt = attendees_ll if is_volunteer else volunteers_ll
        item = ll_alt.find_by_id(submission_id, id_key="submission_id")
        if item:
            ll_target = ll_alt
            sheet_name = "Attendees" if is_volunteer else "Volunteers"
            is_volunteer = not is_volunteer

    if not item:
        return False, f"Submission {submission_id} not found."

    old_status = item.get("status", "Pending")
    item["status"] = new_status
    item["reviewed_by"] = reviewed_by

    ll_target.update(submission_id, item, id_key="submission_id")
    _write_sheet_dicts(sheet_name, ll_target.traverse())

    # Update Registrations sheet as well
    regs = get_registrations()
    for r in regs:
        if r.get("registration_id") == submission_id:
            r["status"] = new_status
            r["reviewed_by"] = reviewed_by
            break
    _write_sheet_dicts("Registrations", regs)

    # Remove from Queue if it was in queue
    submissions_queue.remove_by_id(submission_id, id_key="submission_id")

    # Undo action
    undo_stack.push({
        "type": "REVERT_SUBMISSION_STATUS",
        "submission_id": submission_id,
        "sheet_name": sheet_name,
        "previous_status": old_status,
        "description": f"Undo status change for {submission_id}"
    })

    log_activity(
        reviewed_by,
        f"{new_status.upper()}_SUBMISSION",
        f"{new_status} submission {submission_id} ({item.get('candidate_name')}, {item.get('roll_no')})"
    )
    return True, f"Submission {submission_id} marked as {new_status} by {reviewed_by}."


# --- Attendance & Assignments ---

def mark_attendance(attendance_record: Dict[str, Any], actor: str) -> Tuple[bool, str]:
    records = get_attendance()
    # Check for duplicate attendance for same roll_no & event_id
    for r in records:
        if (r.get("event_id") == attendance_record.get("event_id") and
                r.get("roll_no", "").strip().upper() == attendance_record.get("roll_no", "").strip().upper()):
            return False, f"Attendance already marked for {attendance_record.get('roll_no')} in this event."

    records.append(attendance_record)
    ok, msg = _write_sheet_dicts("Attendance", records)
    if not ok:
        return False, msg

    roll = attendance_record.get("roll_no", "").strip().upper()
    if roll not in member_histories:
        member_histories[roll] = MemberParticipationHistory(roll)
    member_histories[roll].add_event(attendance_record)

    undo_stack.push({
        "type": "DELETE_ATTENDANCE",
        "attendance_id": attendance_record.get("attendance_id"),
        "description": f"Undo attendance {attendance_record.get('attendance_id')}"
    })
    log_activity(actor, "MARK_ATTENDANCE", f"Marked attendance for {attendance_record.get('roll_no')} in event {attendance_record.get('event_title')}")
    return True, "Attendance marked successfully."


def add_assignment(assignment_record: Dict[str, Any], actor: str) -> Tuple[bool, str]:
    records = get_assignments()
    records.append(assignment_record)
    ok, msg = _write_sheet_dicts("Assignments", records)
    if not ok:
        return False, msg

    log_activity(actor, "ASSIGN_TASK", f"Assigned task to volunteer {assignment_record.get('volunteer_roll_no')} for {assignment_record.get('event_title')}")
    return True, "Assignment created successfully."


def update_assignment_status(assignment_id: str, new_status: str, actor: str) -> Tuple[bool, str]:
    records = get_assignments()
    found = False
    for r in records:
        if r.get("assignment_id") == assignment_id:
            r["status"] = new_status
            found = True
            break
    if not found:
        return False, f"Assignment {assignment_id} not found."

    ok, msg = _write_sheet_dicts("Assignments", records)
    if not ok:
        return False, msg
    log_activity(actor, "UPDATE_ASSIGNMENT", f"Updated assignment {assignment_id} status to {new_status}")
    return True, "Assignment updated successfully."


def _rebuild_member_histories() -> None:
    """Rebuilds every member participation linked list from the Attendance sheet."""
    member_histories.clear()
    for at in get_attendance():
        roll = at.get("roll_no", "").strip().upper()
        if roll:
            if roll not in member_histories:
                member_histories[roll] = MemberParticipationHistory(roll)
            member_histories[roll].add_event(at)


def delete_attendance(attendance_id: str, actor: str) -> Tuple[bool, str]:
    records = get_attendance()
    target = next((r for r in records if r.get("attendance_id") == attendance_id), None)
    if not target:
        return False, f"Attendance record {attendance_id} not found."

    remaining = [r for r in records if r.get("attendance_id") != attendance_id]
    ok, msg = _write_sheet_dicts("Attendance", remaining)
    if not ok:
        return False, msg
    _rebuild_member_histories()

    undo_stack.push({
        "type": "RESTORE_ATTENDANCE_ROW",
        "data": dict(target),
        "description": f"Undo delete attendance {attendance_id}"
    })
    log_activity(actor, "DELETE_ATTENDANCE", f"Deleted attendance record {attendance_id}")
    return True, "Attendance record deleted successfully."


def delete_assignment(assignment_id: str, actor: str) -> Tuple[bool, str]:
    records = get_assignments()
    target = next((r for r in records if r.get("assignment_id") == assignment_id), None)
    if not target:
        return False, f"Assignment {assignment_id} not found."

    remaining = [r for r in records if r.get("assignment_id") != assignment_id]
    ok, msg = _write_sheet_dicts("Assignments", remaining)
    if not ok:
        return False, msg

    undo_stack.push({
        "type": "RESTORE_ASSIGNMENT_ROW",
        "data": dict(target),
        "description": f"Undo delete assignment {assignment_id}"
    })
    log_activity(actor, "DELETE_ASSIGNMENT", f"Deleted assignment {assignment_id}")
    return True, "Assignment deleted successfully."


# --- Cabinet Accounts Management ---

def add_cabinet_account(account: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    global cabinet_accounts_list
    for acc in cabinet_accounts_list:
        if acc.get("username", "").strip().lower() == account.get("username", "").strip().lower():
            return False, f"Username '{account.get('username')}' already exists."

    cabinet_accounts_list.append(account)
    ok, msg = _write_sheet_dicts("Cabinet", cabinet_accounts_list)
    if not ok:
        cabinet_accounts_list.remove(account)
        return False, msg

    log_activity(actor, "ADD_CABINET_ACCOUNT", f"Created cabinet account for {account.get('username')} ({account.get('title')})")
    return True, "Cabinet account created successfully."


def update_cabinet_account(username: str, updates: Dict[str, Any], actor: str = "admin") -> Tuple[bool, str]:
    global cabinet_accounts_list
    found = False
    for acc in cabinet_accounts_list:
        if acc.get("username", "").strip().lower() == username.strip().lower():
            acc.update(updates)
            found = True
            break
    if not found:
        return False, f"Account '{username}' not found."

    ok, msg = _write_sheet_dicts("Cabinet", cabinet_accounts_list)
    if not ok:
        return False, msg

    log_activity(actor, "UPDATE_CABINET_ACCOUNT", f"Updated account details for {username}")
    return True, "Cabinet account updated successfully."


def reset_password(username: str, new_password: str, actor: str = "admin") -> Tuple[bool, str]:
    global cabinet_accounts_list
    pwd_hash, salt = hash_password(new_password)
    found = False
    for acc in cabinet_accounts_list:
        if acc.get("username", "").strip().lower() == username.strip().lower():
            acc["password_hash"] = pwd_hash
            acc["salt"] = salt
            found = True
            break
    if not found:
        return False, f"Account '{username}' not found."

    ok, msg = _write_sheet_dicts("Cabinet", cabinet_accounts_list)
    if not ok:
        return False, msg

    log_activity(actor, "RESET_PASSWORD", f"Password reset for {username}")
    return True, f"Password for {username} reset successfully."


# --- Undo Functionality (Stack LIFO) ---

def undo_last_action(actor: str = "admin") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Pops the top operation from undo_stack and reverts the change.
    """
    if undo_stack.is_empty():
        return False, "Nothing to undo. Stack is empty.", None

    action = undo_stack.pop()
    action_type = action.get("type")

    try:
        if action_type == "DELETE_MEMBER":
            member_id = action.get("member_id")
            members_ll.delete_by_id(member_id, id_key="member_id")
            _write_sheet_dicts("Members", members_ll.traverse())

        elif action_type == "RESTORE_MEMBER":
            member_id = action.get("member_id")
            prev_data = action.get("previous_data")
            members_ll.update(member_id, prev_data, id_key="member_id")
            _write_sheet_dicts("Members", members_ll.traverse())

        elif action_type == "INSERT_MEMBER":
            data = action.get("data")
            members_ll.insert_at_end(data)
            _write_sheet_dicts("Members", members_ll.traverse())

        elif action_type == "DELETE_EVENT":
            event_id = action.get("event_id")
            evs = [e for e in schedule_array.get_all() if e.get("event_id") != event_id]
            schedule_array.set_all(evs, date_key="date")
            _write_sheet_dicts("Events", evs)

        elif action_type == "RESTORE_EVENT":
            data = action.get("data")
            schedule_array.append(data, date_key="date")
            _write_sheet_dicts("Events", schedule_array.get_all())

        elif action_type == "DELETE_FORM":
            form_id = action.get("form_id")
            fms = [f for f in get_forms() if f.get("form_id") != form_id]
            _write_sheet_dicts("Forms", fms)

        elif action_type == "RESTORE_FORM":
            form_id = action.get("form_id")
            prev_data = action.get("previous_data")
            fms = get_forms()
            for i, f in enumerate(fms):
                if f.get("form_id") == form_id:
                    fms[i] = prev_data
                    break
            _write_sheet_dicts("Forms", fms)

        elif action_type == "RESTORE_FORM_ROW":
            data = action.get("data")
            fms = get_forms()
            fms.append(data)
            _write_sheet_dicts("Forms", fms)

        elif action_type == "REVERT_SUBMISSION_STATUS":
            sub_id = action.get("submission_id")
            prev_st = action.get("previous_status")
            sheet_name = action.get("sheet_name")
            target_ll = volunteers_ll if sheet_name == "Volunteers" else attendees_ll
            item = target_ll.find_by_id(sub_id, id_key="submission_id")
            if item:
                item["status"] = prev_st
                target_ll.update(sub_id, item, id_key="submission_id")
                _write_sheet_dicts(sheet_name, target_ll.traverse())
            # Also update Registrations sheet
            regs = get_registrations()
            for r in regs:
                if r.get("registration_id") == sub_id:
                    r["status"] = prev_st
                    break
            _write_sheet_dicts("Registrations", regs)

        elif action_type == "DELETE_ATTENDANCE":
            at_id = action.get("attendance_id")
            records = [r for r in get_attendance() if r.get("attendance_id") != at_id]
            _write_sheet_dicts("Attendance", records)
            _rebuild_member_histories()

        elif action_type == "RESTORE_ATTENDANCE_ROW":
            records = get_attendance()
            records.append(action.get("data"))
            _write_sheet_dicts("Attendance", records)
            _rebuild_member_histories()

        elif action_type == "RESTORE_ASSIGNMENT_ROW":
            records = get_assignments()
            records.append(action.get("data"))
            _write_sheet_dicts("Assignments", records)

        elif action_type == "REPLACE_EVENT":
            ev_id = action.get("event_id")
            prev = action.get("previous_data")
            evs = [prev if e.get("event_id") == ev_id else e for e in schedule_array.get_all()]
            schedule_array.set_all(evs, date_key="date")
            _write_sheet_dicts("Events", schedule_array.get_all())

        else:
            return False, f"Unknown action type: {action_type}", action

        log_activity(actor, "UNDO_ACTION", f"Undid action: {action.get('description', action_type)}")
        return True, f"Successfully undid: {action.get('description', action_type)}", action

    except Exception as e:
        log_activity(actor, "UNDO_ERROR", f"Failed to undo: {str(e)}")
        return False, f"Error executing undo: {str(e)}", action


# --- Zip ID Card Files for Download ---

def create_id_cards_zip() -> io.BytesIO:
    """Creates a zip archive in-memory containing all uploaded ID card images."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in UPLOADS_DIR.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(UPLOADS_DIR).as_posix())
    zip_buffer.seek(0)
    return zip_buffer


def save_upload(contents: bytes, form_id: str, filename: str, content_type: str) -> str:
    object_path = f"uploads/{form_id}/{filename}"
    if _BLOB_RUNTIME:
        _ensure_blob_seeded()
        blob_storage.write(object_path, contents, content_type)
        return f"{form_id}/{filename}"
    destination = UPLOADS_DIR / form_id / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)
    return destination.relative_to(UPLOADS_DIR).as_posix()


def read_upload(object_path: str) -> bytes:
    if _BLOB_RUNTIME:
        contents = blob_storage.read(f"uploads/{object_path.lstrip('/')}")
        if contents is None:
            raise FileNotFoundError(object_path)
        return contents
    path = (UPLOADS_DIR / object_path).resolve()
    path.relative_to(UPLOADS_DIR.resolve())
    return path.read_bytes()


def delete_upload(object_path: str) -> None:
    if _BLOB_RUNTIME:
        blob_storage.delete(f"uploads/{object_path.lstrip('/')}")
        return
    path = (UPLOADS_DIR / object_path).resolve()
    path.relative_to(UPLOADS_DIR.resolve())
    if path.is_file():
        path.unlink()


def clear_event_data(form_id: str) -> None:
    """Clears all stored submission data for a specific form/event after download."""
    global members_ll, volunteers_ll, attendees_ll, submissions_queue

    clean_form_id = form_id.strip().lower()

    # Remove from volunteers linked list
    vols = get_volunteers()
    remaining_vols = [v for v in vols if v.get("form_id", "").strip().lower() != clean_form_id]
    volunteers_ll = SinglyLinkedList()
    for v in remaining_vols:
        volunteers_ll.append(v)

    # Remove from attendees linked list
    atts = get_attendees()
    remaining_atts = [a for a in atts if a.get("form_id", "").strip().lower() != clean_form_id]
    attendees_ll = SinglyLinkedList()
    for a in remaining_atts:
        attendees_ll.append(a)

    # Remove from queue
    q_items = submissions_queue.to_list()
    submissions_queue = Queue()
    for item in q_items:
        if item.get("form_id", "").strip().lower() != clean_form_id:
            submissions_queue.enqueue(item)

    # Save changes to Excel
    _write_sheet_dicts("Volunteers", remaining_vols)
    _write_sheet_dicts("Attendees", remaining_atts)

    # If the form is linked to an event_id, also clear attendance and assignments for that event
    forms = get_forms()
    target_event_id = None
    for f in forms:
        if f.get("form_id", "").strip().lower() == clean_form_id:
            target_event_id = f.get("event_id", "").strip().lower()
            break

    if target_event_id:
        all_att = get_attendance()
        remaining_att = [a for a in all_att if a.get("event_id", "").strip().lower() != target_event_id]
        if len(remaining_att) != len(all_att):
            _write_sheet_dicts("Attendance", remaining_att)

        all_asg = get_assignments()
        remaining_asg = [a for a in all_asg if a.get("event_id", "").strip().lower() != target_event_id]
        if len(remaining_asg) != len(all_asg):
            _write_sheet_dicts("Assignments", remaining_asg)

    log_activity("SYSTEM", "CLEAR_EVENT_DATA", f"Cleared all data for form '{form_id}' after Excel download.")
