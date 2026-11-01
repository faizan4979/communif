"""
Comprehensive Test Suite for DDSS.
Tests handcrafted DSA data structures (Stack, Queue, LinkedList, Array, Sorts, Searches)
and FastAPI endpoints for edge cases and security controls:
- Form closed rejection
- File larger than 500 KB rejection
- Wrong file type rejection
- Invalid roll number rejection
- Duplicate submission rejection
- Cabinet trying admin-only action (403 Forbidden)
"""

import os
import io
import shutil
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.main import app
from backend import dsa
from backend import storage
from backend import auth

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_file_storage(monkeypatch, tmp_path):
    """Keep endpoint tests from changing the repository's authoritative files."""
    records_copy = tmp_path / "records.xlsx"
    shutil.copy2(storage.RECORDS_EXCEL_PATH, records_copy)
    activity_copy = tmp_path / "activity_log.txt"
    if storage.ACTIVITY_LOG_PATH.exists():
        shutil.copy2(storage.ACTIVITY_LOG_PATH, activity_copy)
    uploads_copy = tmp_path / "uploads"
    uploads_copy.mkdir()

    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", records_copy)
    monkeypatch.setattr(storage, "ACTIVITY_LOG_PATH", activity_copy)
    monkeypatch.setattr(storage, "UPLOADS_DIR", uploads_copy)
    storage.load_all_records_to_dsa()
    yield


# ============================================================================
# 1. DSA Unit Tests
# ============================================================================

def test_singly_linked_list():
    sll = dsa.SinglyLinkedList()
    assert len(sll) == 0

    # Insert at end
    sll.insert_at_end({"id": "MEM-001", "name": "Ali"})
    sll.insert_at_end({"id": "MEM-002", "name": "Bilal"})
    sll.insert_at_end({"id": "MEM-003", "name": "Chaudhry"})
    assert len(sll) == 3

    # Traverse
    items = sll.traverse()
    assert len(items) == 3
    assert items[0]["name"] == "Ali"
    assert items[2]["name"] == "Chaudhry"

    # Find by ID
    found = sll.find_by_id("MEM-002")
    assert found is not None
    assert found["name"] == "Bilal"
    assert sll.find_by_id("MEM-999") is None

    # Update
    assert sll.update("MEM-002", {"id": "MEM-002", "name": "Bilal Khan"}) is True
    assert sll.find_by_id("MEM-002")["name"] == "Bilal Khan"

    # Delete by ID
    assert sll.delete_by_id("MEM-002") is True
    assert len(sll) == 2
    assert sll.find_by_id("MEM-002") is None
    # Delete non-existent
    assert sll.delete_by_id("NON_EXISTENT") is False


def test_member_participation_history():
    hist = dsa.MemberParticipationHistory("25F-DS-052")
    assert len(hist) == 0

    hist.add_event({"event_id": "EVT-001", "title": "Bootcamp", "role": "Volunteer"})
    hist.add_event({"event_id": "EVT-002", "title": "Summit", "role": "Attendee"})
    assert len(hist) == 2

    records = hist.traverse()
    assert len(records) == 2
    assert records[0]["event_id"] == "EVT-001"
    assert records[1]["event_id"] == "EVT-002"


def test_event_schedule_array():
    arr = dsa.EventScheduleArray()
    arr.append({"title": "Later Event", "date": "2026-11-20"}, date_key="date")
    arr.append({"title": "Earlier Event", "date": "2026-10-15"}, date_key="date")
    arr.append({"title": "Middle Event", "date": "2026-11-01"}, date_key="date")

    items = arr.get_all()
    assert len(items) == 3
    # Check sorted order by date
    assert items[0]["date"] == "2026-10-15"
    assert items[1]["date"] == "2026-11-01"
    assert items[2]["date"] == "2026-11-20"

    # Index access
    assert arr.index_access(0)["title"] == "Earlier Event"
    assert arr.index_access(99) is None

    # Binary search by date
    found, comps = arr.binary_search_by_date("2026-11-01", date_key="date")
    assert found is not None
    assert found["title"] == "Middle Event"
    assert comps > 0

    not_found, _ = arr.binary_search_by_date("2099-01-01", date_key="date")
    assert not_found is None


def test_fifo_queue():
    q = dsa.Queue()
    assert q.is_empty() is True
    assert q.size() == 0
    assert q.peek() is None

    # Enqueue
    q.enqueue({"id": "SUB-1", "val": 100})
    q.enqueue({"id": "SUB-2", "val": 200})
    q.enqueue({"id": "SUB-3", "val": 300})
    assert q.size() == 3
    assert q.is_empty() is False

    # Peek front
    assert q.peek()["id"] == "SUB-1"

    # Dequeue in FIFO order
    first = q.dequeue()
    assert first["id"] == "SUB-1"
    assert q.size() == 2

    second = q.dequeue()
    assert second["id"] == "SUB-2"

    third = q.dequeue()
    assert third["id"] == "SUB-3"
    assert q.is_empty() is True
    assert q.dequeue() is None


def test_lifo_stack():
    stk = dsa.Stack()
    assert stk.is_empty() is True
    assert stk.size() == 0
    assert stk.peek() is None

    # Push
    stk.push({"action": "ADD_1"})
    stk.push({"action": "ADD_2"})
    stk.push({"action": "ADD_3"})
    assert stk.size() == 3
    assert stk.is_empty() is False

    # Peek top
    assert stk.peek()["action"] == "ADD_3"

    # Pop in LIFO order
    top = stk.pop()
    assert top["action"] == "ADD_3"
    assert stk.size() == 2

    second = stk.pop()
    assert second["action"] == "ADD_2"

    third = stk.pop()
    assert third["action"] == "ADD_1"
    assert stk.is_empty() is True
    assert stk.pop() is None


def test_searching_algorithms():
    items = [
        {"id": "01", "name": "Daniyal Khan", "dept": "Data Science"},
        {"id": "02", "name": "Fatima Noor", "dept": "Software Engineering"},
        {"id": "03", "name": "Usman Farooq", "dept": "Data Science"},
        {"id": "04", "name": "Zainab Raza", "dept": "Computer Science"}
    ]

    # Linear Search
    results, comps = dsa.linear_search(items, key="dept", query="Data Science", partial=True)
    assert len(results) == 2
    assert comps == 4

    # Binary Search on sorted items
    sorted_items, _ = dsa.merge_sort(items, key="name")
    match, b_comps = dsa.binary_search(sorted_items, key="name", target_val="Fatima Noor")
    assert match is not None
    assert match["id"] == "02"
    assert b_comps > 0

    no_match, _ = dsa.binary_search(sorted_items, key="name", target_val="Non Existent")
    assert no_match is None


def test_sorting_algorithms():
    items = [
        {"name": "Zubair", "score": 45},
        {"name": "Ali", "score": 88},
        {"name": "Hamza", "score": 72},
        {"name": "Bilal", "score": 90}
    ]

    # Bubble Sort
    b_sorted, b_time = dsa.bubble_sort(items, key="name")
    assert [x["name"] for x in b_sorted] == ["Ali", "Bilal", "Hamza", "Zubair"]
    assert b_time >= 0

    # Insertion Sort
    i_sorted, i_time = dsa.insertion_sort(items, key="name", reverse=True)
    assert [x["name"] for x in i_sorted] == ["Zubair", "Hamza", "Bilal", "Ali"]
    assert i_time >= 0

    # Merge Sort
    m_sorted, m_time = dsa.merge_sort(items, key="name")
    assert [x["name"] for x in m_sorted] == ["Ali", "Bilal", "Hamza", "Zubair"]
    assert m_time >= 0

    # Quick Sort
    q_sorted, q_time = dsa.quick_sort(items, key="name")
    assert [x["name"] for x in q_sorted] == ["Ali", "Bilal", "Hamza", "Zubair"]
    assert q_time >= 0


# ============================================================================
# 2. API Edge Case and Validation Tests
# ============================================================================

def _create_dummy_image(size_bytes: int = 1000, fmt: str = "PNG") -> bytes:
    """Creates in-memory dummy image file."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(10, 50, 100))
    img.save(buf, format=fmt)
    data = buf.getvalue()
    if len(data) < size_bytes:
        data += b"0" * (size_bytes - len(data))
    return data


def test_api_form_closed():
    """Verify backend rejects submission to a closed form."""
    img_data = _create_dummy_image(2000, "PNG")
    files = {"id_card_picture": ("id.png", img_data, "image/png")}
    data = {
        "form_id": "FORM-003",  # FORM-003 is created as Closed
        "candidate_name": "Test Candidate",
        "roll_no": "25F-DS-052",
        "phone_no": "03001234567",
        "department": "Data Science"
    }
    resp = client.post("/api/public/submit", data=data, files=files)
    assert resp.status_code == 400
    assert "Form is closed" in resp.json().get("detail", "")


def test_api_file_larger_than_500kb():
    """Verify backend rejects file exceeding 500 KB limit (512,000 bytes)."""
    # Create 550 KB file
    large_bytes = b"0" * 563200
    files = {"id_card_picture": ("large.png", large_bytes, "image/png")}
    data = {
        "form_id": "FORM-001",
        "candidate_name": "Large File Candidate",
        "roll_no": "25F-DS-076",
        "phone_no": "03001234567",
        "department": "Data Science"
    }
    resp = client.post("/api/public/submit", data=data, files=files)
    assert resp.status_code == 400
    detail = resp.json().get("detail", "").lower()
    assert "too large" in detail or "500 kb" in detail


def test_api_wrong_file_type():
    """Verify backend rejects non-image or invalid format."""
    fake_txt = b"Hello, this is a plain text file pretending to be an image."
    files = {"id_card_picture": ("fake.txt", fake_txt, "text/plain")}
    data = {
        "form_id": "FORM-001",
        "candidate_name": "Fake Image Candidate",
        "roll_no": "25F-DS-085",
        "phone_no": "03001234567",
        "department": "Data Science"
    }
    resp = client.post("/api/public/submit", data=data, files=files)
    assert resp.status_code == 400
    assert "not a valid or readable image" in resp.json().get("detail", "") or "Invalid file type" in resp.json().get("detail", "")


def test_api_invalid_roll_number():
    """Verify backend rejects invalid roll formats and unlisted students."""
    img_data = _create_dummy_image(2000, "PNG")

    # 1. Invalid Format (CS instead of DS)
    files = {"id_card_picture": ("id.png", img_data, "image/png")}
    data_bad_format = {
        "form_id": "FORM-001",
        "candidate_name": "CS Student",
        "roll_no": "25F-CS-052",
        "phone_no": "03001234567",
        "department": "Computer Science"
    }
    resp1 = client.post("/api/public/submit", data=data_bad_format, files=files)
    assert resp1.status_code == 400
    assert "Invalid roll number format" in resp1.json().get("detail", "")

    # 2. Well-formatted DS roll number but NOT in allowed whitelist (e.g. 25F-DS-999)
    files2 = {"id_card_picture": ("id.png", img_data, "image/png")}
    data_unlisted = {
        "form_id": "FORM-001",
        "candidate_name": "Unlisted Student",
        "roll_no": "25F-DS-999",
        "phone_no": "03001234567",
        "department": "Data Science"
    }
    resp2 = client.post("/api/public/submit", data=data_unlisted, files=files2)
    assert resp2.status_code == 400
    assert "not in the allowed university Data Science student list" in resp2.json().get("detail", "")


def test_api_duplicate_submission():
    """Verify backend rejects second submission for the same roll number and form."""
    img_data = _create_dummy_image(2000, "PNG")
    roll = "25F-DS-023"

    # Clean any prior test submissions for this roll number to ensure test idempotency
    vols = [v for v in storage.get_volunteers() if v.get("roll_no") != roll]
    storage._write_sheet_dicts("Volunteers", vols)
    regs = [r for r in storage.get_registrations() if r.get("roll_no") != roll]
    storage._write_sheet_dicts("Registrations", regs)
    storage.volunteers_ll.delete_by_id(roll, id_key="roll_no")

    files1 = {"id_card_picture": ("id.png", img_data, "image/png")}
    data = {
        "form_id": "FORM-001",
        "candidate_name": "Duplicate Tester",
        "roll_no": roll,
        "phone_no": "03001234567",
        "department": "Data Science"
    }

    # First submission -> should succeed
    resp1 = client.post("/api/public/submit", data=data, files=files1)
    assert resp1.status_code == 200
    assert resp1.json().get("success") is True

    # Second submission with same roll number and form -> should be rejected
    files2 = {"id_card_picture": ("id.png", img_data, "image/png")}
    resp2 = client.post("/api/public/submit", data=data, files=files2)
    assert resp2.status_code == 400
    assert resp2.json().get("detail") == (
        "An application for this roll number has already been submitted for the selected form."
    )


def test_cabinet_trying_admin_only_action():
    """Verify cabinet member is forbidden (403) from executing admin-only routes."""
    # 1. Login as cabinet member 'president'
    login_resp = client.post("/api/auth/login", json={"username": "president", "password": "President@123"})
    assert login_resp.status_code == 200
    token = login_resp.json().get("token")
    headers = {"X-Auth-Token": token}

    # 2. Attempt admin-only action: delete a form
    del_resp = client.delete("/api/forms/FORM-001", headers=headers)
    assert del_resp.status_code == 403
    assert "Forbidden" in del_resp.json().get("detail", "")

    # 3. Attempt admin-only action: trigger undo stack
    undo_resp = client.post("/api/admin/undo", headers=headers)
    assert undo_resp.status_code == 403
    assert "Forbidden" in undo_resp.json().get("detail", "")

    # 4. Attempt admin-only action: access audit log
    audit_resp = client.get("/api/admin/audit-log", headers=headers)
    assert audit_resp.status_code == 403
    assert "Forbidden" in audit_resp.json().get("detail", "")
