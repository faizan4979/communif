"""Small server-side adapter for Vercel Blob private storage."""

import os
import uuid
from typing import Optional


class BlobStorageError(RuntimeError):
    """Raised when Vercel Blob storage is unavailable or rejects an operation."""


def configured() -> bool:
    return bool(
        os.getenv("BLOB_READ_WRITE_TOKEN")
        or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN")
        or os.getenv("BLOB_STORE_ID")
    )


def _client():
    if not configured():
        raise BlobStorageError(
            "Persistent file storage is not configured on the backend."
        )
    try:
        from vercel import blob
    except ImportError as exc:
        raise BlobStorageError(
            "Persistent file storage support is unavailable in this deployment."
        ) from exc
    return blob.sync


def read(pathname: str) -> Optional[bytes]:
    try:
        result = _client().get_blob(pathname, access="private")
    except BlobStorageError:
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "BlobNotFoundError":
            return None
        raise BlobStorageError("Persistent file storage read failed.") from exc
    return result.body


def write(pathname: str, contents: bytes, content_type: str = "application/octet-stream") -> None:
    try:
        _client().put_blob(
            pathname,
            contents,
            access="private",
            content_type=content_type,
            allow_overwrite=True,
        )
    except BlobStorageError:
        raise
    except Exception as exc:
        raise BlobStorageError("Persistent file storage write failed.") from exc


def delete(pathname: str) -> None:
    try:
        _client().delete_blob(pathname)
    except BlobStorageError:
        raise
    except Exception as exc:
        if exc.__class__.__name__ != "BlobNotFoundError":
            raise BlobStorageError("Persistent file storage delete failed.") from exc


def health_check() -> dict[str, bool]:
    """Runs a harmless private Blob round-trip and removes its object."""
    if not configured():
        return {
            "blob_configured": False,
            "store_connection_detected": False,
            "read_available": False,
            "write_available": False,
            "delete_available": False,
        }

    pathname = f"diagnostics/storage-health-{uuid.uuid4().hex}.txt"
    payload = b"DDSS storage health check"
    write_available = False
    read_available = False
    delete_available = False
    try:
        write(pathname, payload, "text/plain")
        write_available = True
        read_available = read(pathname) == payload
        delete(pathname)
        delete_available = read(pathname) is None
    finally:
        if not delete_available:
            try:
                delete(pathname)
            except BlobStorageError:
                pass
    return {
        "blob_configured": True,
        "store_connection_detected": True,
        "read_available": read_available,
        "write_available": write_available,
        "delete_available": delete_available,
    }
