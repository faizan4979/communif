from pathlib import Path

import openpyxl
import pytest
from fastapi import HTTPException

from backend import auth, main, storage
from backend.models import LoginRequest


PASSWORD = "Synthetic-Test-Only!"


def _write_accounts(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Cabinet"
    sheet.append(storage.SHEET_SCHEMAS["Cabinet"])
    for username, role, status, password in rows:
        password_hash, salt = auth.hash_password(password)
        sheet.append([
            username,
            f"{username.title()} Test",
            "Test Role",
            role,
            f"{username}@example.test",
            "00000000000",
            status,
            password_hash,
            salt,
            "2026-10-29 00:00:00",
        ])
    workbook.save(path)


@pytest.fixture
def synthetic_accounts(tmp_path, monkeypatch):
    workbook_path = tmp_path / "records.xlsx"
    _write_accounts(
        workbook_path,
        [
            ("admin", "Admin", "Active", PASSWORD),
            ("cabinet", "Cabinet", "Active", PASSWORD),
            ("inactive", "Cabinet", "Inactive", PASSWORD),
        ],
    )
    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", workbook_path)
    monkeypatch.setattr(storage, "_BLOB_RUNTIME", False)
    monkeypatch.setattr(
        storage,
        "get_cabinet_accounts",
        lambda: storage._read_sheet_dicts("Cabinet"),
    )
    monkeypatch.setattr(storage, "log_activity", lambda *args: None)
    auth.ACTIVE_SESSIONS.clear()
    return workbook_path


def _login(username: str, password: str):
    return main.login(LoginRequest(username=username, password=password))


def test_admin_and_cabinet_login_return_normalized_roles(synthetic_accounts):
    admin = _login(" ADMIN ", PASSWORD)
    cabinet = _login("cabinet", PASSWORD)

    assert admin.role == "admin"
    assert cabinet.role == "cabinet"
    assert auth.get_session(admin.token)["role"] == "admin"
    assert auth.get_session(cabinet.token)["role"] == "cabinet"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("unknown", PASSWORD),
        ("admin", "wrong"),
        ("", PASSWORD),
        ("admin", ""),
    ],
)
def test_invalid_login_uses_exact_generic_error(synthetic_accounts, username, password):
    with pytest.raises(HTTPException) as error:
        _login(username, password)

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid username or password."


def test_inactive_account_is_rejected(synthetic_accounts):
    with pytest.raises(HTTPException) as error:
        _login("inactive", PASSWORD)

    assert error.value.status_code == 403


def test_invalid_hash_format_is_rejected_without_exception(tmp_path, monkeypatch):
    workbook_path = tmp_path / "records.xlsx"
    _write_accounts(workbook_path, [("broken", "cabinet", "Active", PASSWORD)])
    workbook = openpyxl.load_workbook(workbook_path)
    sheet = workbook["Cabinet"]
    sheet.cell(row=2, column=8).value = "not-a-hash"
    workbook.save(workbook_path)
    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", workbook_path)
    monkeypatch.setattr(storage, "_BLOB_RUNTIME", False)
    monkeypatch.setattr(
        storage,
        "get_cabinet_accounts",
        lambda: storage._read_sheet_dicts("Cabinet"),
    )
    monkeypatch.setattr(storage, "log_activity", lambda *args: None)

    with pytest.raises(HTTPException) as error:
        _login("broken", PASSWORD)

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid username or password."


def test_duplicate_username_is_rejected_safely(tmp_path, monkeypatch):
    workbook_path = tmp_path / "records.xlsx"
    _write_accounts(
        workbook_path,
        [
            ("duplicate", "cabinet", "Active", PASSWORD),
            ("DUPLICATE", "admin", "Active", PASSWORD),
        ],
    )
    monkeypatch.setattr(storage, "RECORDS_EXCEL_PATH", workbook_path)
    monkeypatch.setattr(storage, "_BLOB_RUNTIME", False)
    monkeypatch.setattr(
        storage,
        "get_cabinet_accounts",
        lambda: storage._read_sheet_dicts("Cabinet"),
    )
    monkeypatch.setattr(storage, "log_activity", lambda *args: None)

    with pytest.raises(HTTPException) as error:
        _login(" duplicate ", PASSWORD)

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid username or password."


def test_logout_invalidates_session(synthetic_accounts):
    login = _login("cabinet", PASSWORD)
    assert auth.invalidate_session(login.token) is True
    assert auth.get_session(login.token) is None


def test_login_ui_does_not_expose_credentials_or_duplicate_error_prefix():
    app_js = (Path(__file__).parents[1] / "web" / "app.js").read_text(encoding="utf-8")
    streamlit_app = (Path(__file__).parents[1] / "frontend" / "app.py").read_text(encoding="utf-8")

    for secret in ("AdminPassword@123", "President@123", "VicePres@123"):
        assert secret not in app_js
        assert secret not in streamlit_app
    assert "notify(`Authentication failed:" not in app_js
    assert "st.error(f\"Authentication failed:" not in streamlit_app
