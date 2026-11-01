import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import auth, storage
from backend.main import app


client = TestClient(app)


def image_bytes(format_name="PNG", size=(2, 2)):
    image = Image.new("RGB", size, color="white")
    output = io.BytesIO()
    image.save(output, format=format_name)
    return output.getvalue()


@pytest.fixture
def isolated_submission(monkeypatch, tmp_path):
    form = {
        "form_id": "TEST-FORM",
        "event_title": "Synthetic Test Event",
        "form_type": "Volunteer",
        "is_open_manual": "True",
        "open_time": "",
        "close_time": "",
        "max_seats": "",
    }
    monkeypatch.setattr(storage, "get_forms", lambda: [form])
    monkeypatch.setattr(storage, "get_registrations", lambda: [])
    monkeypatch.setattr(auth, "is_roll_number_allowed", lambda roll: (True, ""))
    monkeypatch.setattr(storage, "log_activity", lambda *args: None)
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(
        storage,
        "add_submission",
        lambda submission, form_type: (True, "Submission recorded successfully."),
    )
    return form


def submission_data(form_id="TEST-FORM"):
    return {
        "form_id": form_id,
        "candidate_name": "Synthetic Student",
        "roll_no": "25F-DS-999",
        "phone_no": "03001234567",
        "department": "Data Science",
    }


def test_successful_multipart_submission(isolated_submission):
    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["reference_number"].startswith("VOL-")


def test_missing_required_field_returns_422(isolated_submission):
    data = submission_data()
    data.pop("phone_no")

    response = client.post(
        "/api/public/submit",
        data=data,
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "phone_no"


def test_invalid_roll_number_returns_400(isolated_submission, monkeypatch):
    monkeypatch.setattr(
        auth,
        "is_roll_number_allowed",
        lambda roll: (False, "Roll number is not allowed."),
    )

    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Roll number is not allowed."


def test_invalid_department_returns_400(isolated_submission):
    data = submission_data()
    data["department"] = "Synthetic Department"

    response = client.post(
        "/api/public/submit",
        data=data,
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid department."


def test_duplicate_registration_returns_400(isolated_submission, monkeypatch):
    monkeypatch.setattr(
        storage,
        "get_registrations",
        lambda: [{"form_id": "TEST-FORM", "roll_no": "25F-DS-999"}],
    )

    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "An application for this roll number has already been submitted for the selected form."
    )


def test_invalid_image_type_returns_400(isolated_submission):
    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
    assert "valid or readable image" in response.json()["detail"]


def test_oversized_image_returns_400(isolated_submission):
    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.png", b"x" * 512001, "image/png")},
    )

    assert response.status_code == 400
    assert "too large" in response.json()["detail"]


def test_unknown_form_returns_404(isolated_submission):
    response = client.post(
        "/api/public/submit",
        data=submission_data("UNKNOWN-FORM"),
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 404


def test_closed_form_returns_400(isolated_submission):
    isolated_submission["is_open_manual"] = "False"

    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert "closed" in response.json()["detail"].lower()


def test_cors_preflight_for_production_frontend(isolated_submission):
    response = client.options(
        "/api/public/submit",
        headers={
            "Origin": "https://ddss-project.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ddss-project.vercel.app"


def test_duplicate_registration_message_is_exact(isolated_submission, monkeypatch):
    monkeypatch.setattr(
        storage,
        "get_registrations",
        lambda: [{"form_id": "TEST-FORM", "roll_no": "25F-DS-999"}],
    )

    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "An application for this roll number has already been submitted for the selected form."
    )


def test_storage_failure_returns_structured_503(isolated_submission, monkeypatch):
    monkeypatch.setattr(
        storage,
        "add_submission",
        lambda submission, form_type: (
            False,
            "Registration storage is unavailable.",
        ),
    )

    response = client.post(
        "/api/public/submit",
        data=submission_data(),
        files={"id_card_picture": ("synthetic.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Submission could not be saved because persistent file storage is temporarily unavailable. "
        "Please try again later."
    )
