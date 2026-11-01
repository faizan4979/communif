import hashlib
import io
import importlib
import shutil

import openpyxl
from fastapi.testclient import TestClient

from backend import storage


def _file_hash(path):
    return hashlib.sha256(path.read_bytes()).digest()


def test_local_initialization_creates_missing_workbook_structure(monkeypatch, tmp_path):
    records_path = tmp_path / "records.xlsx"
    uploads_path = tmp_path / "uploads"
    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", records_path)
    monkeypatch.setattr(storage, "UPLOADS_DIR", uploads_path)
    monkeypatch.setattr(storage, "ACTIVITY_LOG_PATH", tmp_path / "activity_log.txt")

    storage.init_storage(read_only=False)

    workbook = openpyxl.load_workbook(records_path, read_only=True)
    assert "Queue" in workbook.sheetnames
    assert "Participation History" in workbook.sheetnames
    assert uploads_path.is_dir()


def test_vercel_initialization_reads_without_saving(monkeypatch, tmp_path):
    records_path = tmp_path / "records.xlsx"
    shutil.copy2(storage.RECORDS_EXCEL_PATH, records_path)
    before_hash = _file_hash(records_path)
    uploads_path = tmp_path / "uploads"
    before_sheets = openpyxl.load_workbook(records_path, read_only=True).sheetnames
    save_called = False

    def fail_save(*args, **kwargs):
        nonlocal save_called
        save_called = True
        raise AssertionError("Vercel initialization must not save records.xlsx")

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", records_path)
    monkeypatch.setattr(storage, "UPLOADS_DIR", uploads_path)
    monkeypatch.setattr(openpyxl.workbook.workbook.Workbook, "save", fail_save)

    storage.init_storage()

    assert not save_called
    assert _file_hash(records_path) == before_hash
    assert openpyxl.load_workbook(records_path, read_only=True).sheetnames == before_sheets
    assert not uploads_path.exists()


def test_vercel_backend_import_and_health_do_not_save(monkeypatch, tmp_path):
    records_path = tmp_path / "records.xlsx"
    shutil.copy2(storage.RECORDS_EXCEL_PATH, records_path)
    before_hash = _file_hash(records_path)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", records_path)
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(storage, "ACTIVITY_LOG_PATH", tmp_path / "activity_log.txt")

    def fail_save(*args, **kwargs):
        raise AssertionError("Vercel backend import must not save records.xlsx")

    monkeypatch.setattr(openpyxl.workbook.workbook.Workbook, "save", fail_save)
    import backend.main

    module = importlib.reload(backend.main)
    response = TestClient(module.app).get("/health")
    assert response.status_code == 200
    assert _file_hash(records_path) == before_hash


def test_form_description_migration_updates_only_target_blob_cell(monkeypatch):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Forms"
    sheet.append(["Form ID", "Description", "Event ID"])
    sheet.append(["FORM-001", "Old description", "EVT-001"])
    sheet.append(["FORM-002", "Keep this description", "EVT-002"])
    source = io.BytesIO()
    workbook.save(source)

    blob_objects = {"records.xlsx": source.getvalue()}
    monkeypatch.setattr(storage, "_BLOB_RUNTIME", True)
    monkeypatch.setattr(storage.blob_storage, "read", lambda path: blob_objects.get(path))
    monkeypatch.setattr(
        storage.blob_storage,
        "write",
        lambda path, contents, content_type: blob_objects.__setitem__(path, contents),
    )

    ok, message = storage.migrate_form_description(
        "FORM-001",
        "Old description",
        "New description",
    )

    assert ok
    assert "updated" in message
    result = openpyxl.load_workbook(io.BytesIO(blob_objects["records.xlsx"]), read_only=True)
    rows = list(result["Forms"].values)
    result.close()
    assert rows[1] == ("FORM-001", "New description", "EVT-001")
    assert rows[2] == ("FORM-002", "Keep this description", "EVT-002")


def test_blob_reads_refresh_the_current_production_workbook(monkeypatch, tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Forms"
    sheet.append(["Form ID", "Description"])
    sheet.append(["FORM-001", "Current Blob description"])
    source = io.BytesIO()
    workbook.save(source)

    destination = tmp_path / "records.xlsx"
    destination.write_bytes(b"stale snapshot")
    monkeypatch.setattr(storage, "_BLOB_RUNTIME", True)
    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", destination)
    monkeypatch.setattr(storage.blob_storage, "read", lambda path: source.getvalue())

    storage._refresh_blob_workbook()

    assert destination.read_bytes() == source.getvalue()
