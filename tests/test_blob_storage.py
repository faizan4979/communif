import pytest

from backend import auth, blob_storage


class _Result:
    def __init__(self, body):
        self.body = body


class BlobNotFoundError(Exception):
    pass


class _FakeBlobClient:
    def __init__(self):
        self.objects = {}

    def get_blob(self, pathname, access):
        if pathname not in self.objects:
            raise BlobNotFoundError("missing")
        return _Result(self.objects[pathname])

    def put_blob(self, pathname, body, **kwargs):
        self.objects[pathname] = bytes(body)

    def delete_blob(self, pathname):
        self.objects.pop(pathname, None)


def test_blob_adapter_round_trip_and_missing_object(monkeypatch):
    client = _FakeBlobClient()
    monkeypatch.setattr(blob_storage, "configured", lambda: True)
    monkeypatch.setattr(blob_storage, "_client", lambda: client)

    assert blob_storage.read("missing") is None
    blob_storage.write("records.xlsx", b"workbook", "application/test")
    assert blob_storage.read("records.xlsx") == b"workbook"
    blob_storage.delete("records.xlsx")
    assert blob_storage.read("records.xlsx") is None


def test_blob_adapter_requires_configuration(monkeypatch):
    monkeypatch.setattr(blob_storage, "configured", lambda: False)

    with pytest.raises(blob_storage.BlobStorageError, match="not configured"):
        blob_storage.write("records.xlsx", b"workbook")


def test_store_id_is_sufficient_for_oidc_configuration(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("BLOB_STORE_ID", "store_example")
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)

    assert blob_storage.configured()


def test_health_check_deletes_diagnostic_object(monkeypatch):
    client = _FakeBlobClient()
    monkeypatch.setattr(blob_storage, "configured", lambda: True)
    monkeypatch.setattr(blob_storage, "_client", lambda: client)

    result = blob_storage.health_check()

    assert result == {
        "blob_configured": True,
        "store_connection_detected": True,
        "read_available": True,
        "write_available": True,
        "delete_available": True,
    }
    assert client.objects == {}


def test_name_validation_normalizes_and_accepts_common_names():
    assert auth.normalize_candidate_name("  muhammad   ali  ") == "Muhammad Ali"
    assert auth.normalize_candidate_name("ali-shan") == "Ali-Shan"
    assert auth.normalize_candidate_name("o'connor") == "O'Connor"
    assert auth.validate_candidate_name("  Anne-Marie   O'Neil  ") == (True, "")
    assert auth.validate_candidate_name("---") == (
        False,
        "Enter a valid full name using letters, spaces, hyphens, or apostrophes.",
    )
