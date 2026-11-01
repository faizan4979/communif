"""
Data Models for DDSS (Dawood Data Science Society)
Defines Pydantic schemas and data containers for Members, Volunteers, Attendees,
Events, Forms, Registrations, Attendance, Assignments, and Cabinet members.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str  # "admin" or "cabinet"
    full_name: str
    title: Optional[str] = None


class MemberModel(BaseModel):
    member_id: str
    name: str
    roll_no: str
    phone: str
    department: str
    email: Optional[str] = ""
    status: str = "Active"
    joined_at: str


class EventModel(BaseModel):
    event_id: str
    title: str
    description: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    start_time: Optional[str] = ""
    end_time: Optional[str] = ""
    venue: str
    status: str = "Upcoming"  # Upcoming, Ongoing, Completed, Cancelled
    created_by: str = "admin"


class FormModel(BaseModel):
    form_id: str
    event_id: str
    event_title: str
    form_type: str  # "Volunteer" or "Attendee"
    description: str
    is_open_manual: bool = True
    open_time: Optional[str] = ""  # YYYY-MM-DD HH:MM:SS
    close_time: Optional[str] = ""  # YYYY-MM-DD HH:MM:SS
    max_seats: Optional[int] = None
    created_at: str


class SubmissionCreate(BaseModel):
    form_id: str
    candidate_name: str
    roll_no: str
    phone_no: str
    department: str
    email: Optional[str] = ""
    university_email: str


class SubmissionRecord(BaseModel):
    submission_id: str
    form_id: str
    event_title: str
    candidate_name: str
    roll_no: str
    phone_no: str
    department: str
    email: Optional[str] = ""
    university_email: str = ""
    id_card_file: str
    submitted_at: str
    status: str = "Pending"  # Pending, Approved, Rejected
    reviewed_by: str = "Unassigned"


class AttendanceRecord(BaseModel):
    attendance_id: str
    event_id: str
    event_title: str
    roll_no: str
    candidate_name: str
    role: str  # "Volunteer" or "Attendee"
    marked_at: str
    marked_by: str
    status: str = "Present"  # Present, Absent


class AssignmentRecord(BaseModel):
    assignment_id: str
    event_id: str
    event_title: str
    volunteer_roll_no: str
    volunteer_name: str
    task_description: str
    assigned_by: str
    status: str = "Assigned"  # Assigned, In Progress, Completed
    assigned_at: str


class CabinetAccount(BaseModel):
    username: str
    full_name: str
    title: str
    email: str = ""
    phone: str = ""
    status: str = "Active"
    password_hash: str
    salt: str
    created_at: str


class CabinetAccountCreate(BaseModel):
    username: str
    full_name: str
    title: str
    password: str
    email: Optional[str] = ""
    phone: Optional[str] = ""


class CabinetAccountUpdate(BaseModel):
    full_name: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class SearchRequest(BaseModel):
    dataset: str  # "members", "volunteers", "attendees", "events", "forms", "cabinet"
    key: str
    query: str
    algorithm: str = "linear"  # "linear" or "binary"
    partial: bool = True


class SortRequest(BaseModel):
    dataset: str
    key: str
    algorithm: str = "bubble"  # "bubble", "insertion", "merge", "quick"
    reverse: bool = False


class UndoResponse(BaseModel):
    success: bool
    message: str
    action: Optional[Dict[str, Any]] = None
