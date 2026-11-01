"""
Authentication, Authorization, and Roll Number Validation Module for DDSS.
Uses hashlib.pbkdf2_hmac with salt for password security.
"""

import csv
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from fastapi import Header, HTTPException, status

ROLL_PATTERN = re.compile(r"^\d{2}[A-Za-z]-[A-Za-z]{2,5}-\d{2,4}$")
DUET_EMAIL_PATTERN = re.compile(r"^\d{2}[a-z]-[a-z]{2,5}-\d{2,4}@students\.duet\.edu\.pk$", re.IGNORECASE)
PAK_PHONE_PATTERN = re.compile(r"^(\+923\d{9}|03\d{9})$")
NAME_PATTERN = re.compile(r"^[A-Za-z\s'-]{3,60}$")

ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROLL_FILE = PROJECT_ROOT / "allowed_roll_numbers.csv"


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hashes a password with PBKDF2 HMAC SHA-256."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return hashed, salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Verifies that password matches the supplied hash and salt."""
    if (
        not isinstance(salt, str)
        or not re.fullmatch(r"[0-9a-fA-F]{32}", salt)
        or not isinstance(expected_hash, str)
        or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash)
    ):
        return False
    computed_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, expected_hash)


def create_session(username: str, role: str, full_name: str, title: str = "") -> str:
    """Generates a secure token and registers a session."""
    token = secrets.token_hex(32)
    ACTIVE_SESSIONS[token] = {
        "username": username,
        "role": role,
        "full_name": full_name,
        "title": title,
    }
    return token


def invalidate_session(token: str) -> bool:
    """Logs out by removing the token."""
    if token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[token]
        return True
    return False


def get_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Retrieves a session dict for a token if valid."""
    if not token:
        return None
    return ACTIVE_SESSIONS.get(token)


def get_current_user_from_header(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Extracts the current user from an authentication header."""
    token = None
    if x_auth_token:
        token = x_auth_token
    elif authorization:
        parts = authorization.split()
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else authorization

    session = get_session(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication credentials",
        )
    return session


def require_role(allowed_roles: list[str]):
    """Decorator / dependency factory enforcing user roles."""
    def _role_checker(
        authorization: Optional[str] = Header(None),
        x_auth_token: Optional[str] = Header(None),
    ) -> Dict[str, Any]:
        user = get_current_user_from_header(authorization, x_auth_token)
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: action requires one of {allowed_roles}",
            )
        return user
    return _role_checker


def valid_roll_no(roll: str) -> bool:
    """Validates the standard DUET Data Science roll number format."""
    return bool(roll and ROLL_PATTERN.fullmatch(roll.strip().upper()))


def get_allowed_roll_numbers() -> Set[str]:
    """Reads allowed roll numbers from allowed_roll_numbers.csv."""
    if os.getenv("VERCEL", "").strip().lower() in {"1", "true", "yes"}:
        try:
            from backend import blob_storage
            contents = blob_storage.read("allowed_roll_numbers.csv")
            if contents is not None:
                allowed: Set[str] = set()
                for row in csv.reader(contents.decode("utf-8-sig").splitlines()):
                    if row:
                        item = row[0].strip().upper()
                        if item and item != "ROLL_NO" and valid_roll_no(item):
                            allowed.add(item)
                return allowed
        except Exception:
            pass
    allowed: Set[str] = set()
    if not ALLOWED_ROLL_FILE.exists():
        return allowed

    with ALLOWED_ROLL_FILE.open(mode="r", encoding="utf-8-sig", newline="") as file:
        for row in csv.reader(file):
            if not row:
                continue
            item = row[0].strip().upper()
            if item and item != "ROLL_NO" and valid_roll_no(item):
                allowed.add(item)
    return allowed


def save_allowed_roll_numbers(roll_list: list[str]) -> None:
    """Overwrites allowed_roll_numbers.csv with validated roll numbers."""
    cleaned = sorted({
        roll.strip().upper()
        for roll in roll_list
        if valid_roll_no(roll.strip().upper())
    })
    try:
        if os.getenv("VERCEL", "").strip().lower() in {"1", "true", "yes"}:
            from backend import blob_storage
            if not blob_storage.configured():
                raise RuntimeError(
                    "Allowed roll-number storage is unavailable. Configure persistent file storage."
                )
            blob_storage.write(
                "allowed_roll_numbers.csv",
                ("roll_no\n" + "".join(f"{roll}\n" for roll in cleaned)).encode("utf-8"),
                "text/csv",
            )
            return
        with ALLOWED_ROLL_FILE.open(mode="w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["roll_no"])
            writer.writerows([[roll] for roll in cleaned])
    except OSError as exc:
        raise RuntimeError(
            "Allowed roll-number storage is unavailable. Please try again later."
        ) from exc


def is_roll_number_allowed(roll: str) -> Tuple[bool, str]:
    """Checks that a roll number has a valid format (Batch-Dept-Number)."""
    clean_roll = roll.strip().upper()
    if not valid_roll_no(clean_roll):
        return False, (
            f"Invalid roll number format: '{roll}'. "
            "Expected format like 25F-DS-052 (e.g. BatchF-DEPT-Number)."
        )
    return True, ""


def validate_university_email(email: str, roll_no: Optional[str] = None) -> Tuple[bool, str]:
    """Validates that an email follows DUET student email format and matches roll number."""
    clean_email = email.strip().lower()
    if not clean_email.endswith("@students.duet.edu.pk"):
        return False, (
            f"Invalid university email: '{email}'. "
            "Only official DUET student email addresses ending in @students.duet.edu.pk are accepted."
        )
    if not DUET_EMAIL_PATTERN.fullmatch(clean_email):
        return False, (
            f"Invalid university email format: '{email}'. "
            "Expected format like 25f-ds-076@students.duet.edu.pk"
        )
    if roll_no:
        email_roll_part = clean_email.split("@")[0].upper()
        if email_roll_part != roll_no.strip().upper():
            return False, (
                f"The roll number in university email ({clean_email.split('@')[0]}) "
                f"does not match the entered roll number ({roll_no.strip().upper()})."
            )
    return True, ""


def validate_candidate_name(name: str) -> Tuple[bool, str]:
    """Validates and normalizes a candidate name."""
    clean_name = normalize_candidate_name(name)
    if not NAME_PATTERN.fullmatch(clean_name):
        return False, (
            "Enter a valid full name using letters, spaces, hyphens, or apostrophes."
        )
    if not any(char.isalpha() for char in clean_name):
        return False, "Enter a valid full name using letters, spaces, hyphens, or apostrophes."
    return True, ""


def normalize_candidate_name(name: str) -> str:
    """Trims, collapses spaces, and capitalizes name components safely."""
    collapsed = re.sub(r"\s+", " ", name.strip())
    return collapsed.title()


def validate_phone_number(phone: str) -> Tuple[bool, str]:
    """Validates a Pakistani phone number."""
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    if not PAK_PHONE_PATTERN.fullmatch(clean_phone):
        return False, (
            "Enter a valid Pakistani mobile number, for example 03001234567."
        )
    return True, ""
