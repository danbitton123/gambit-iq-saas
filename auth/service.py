from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from config import ROOT


USERS_DB_PATH = Path(os.getenv("GAMBIT_USERS_DB", ROOT / "data" / "users.db"))
PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str
    display_name: str
    auth_provider: str


class AuthError(ValueError):
    pass


def _connect() -> sqlite3.Connection:
    USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(USERS_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript("""
      CREATE TABLE IF NOT EXISTS users(
        user_id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,display_name TEXT NOT NULL,
        password_hash TEXT,password_salt TEXT,auth_provider TEXT NOT NULL,
        created_at TEXT NOT NULL,last_login_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS data_imports(
        import_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,filename TEXT NOT NULL,status TEXT NOT NULL,
        rows_loaded INTEGER NOT NULL DEFAULT 0,manifest_json TEXT,error_message TEXT,created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
      );
      CREATE INDEX IF NOT EXISTS idx_imports_user_created ON data_imports(user_id,created_at DESC);
    """)
    return connection


def ensure_user_database() -> None:
    with _connect():
        pass


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not EMAIL_PATTERN.match(value):
        raise AuthError("Enter a valid email address.")
    return value


def _validate_password(password: str) -> None:
    if len(password) < 10 or not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"\d", password):
        raise AuthError("Password must contain at least 10 characters, uppercase, lowercase and a number.")


def _password_hash(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), PASSWORD_ITERATIONS).hex()


def _row_user(row: sqlite3.Row) -> AuthUser:
    return AuthUser(row["user_id"], row["email"], row["display_name"], row["auth_provider"])


def register_email(email: str, password: str, display_name: str) -> AuthUser:
    email = _normalize_email(email)
    name = display_name.strip()
    if len(name) < 2:
        raise AuthError("Enter your full name.")
    _validate_password(password)
    salt = secrets.token_hex(32)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _connect() as connection:
            user_id = uuid4().hex
            connection.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?,?)", (
                user_id, email, name, _password_hash(password, salt), salt, "email", now, now,
            ))
            return AuthUser(user_id, email, name, "email")
    except sqlite3.IntegrityError as exc:
        raise AuthError("An account already exists for this email address.") from exc


def authenticate_email(email: str, password: str) -> AuthUser:
    try:
        email = _normalize_email(email)
    except AuthError as exc:
        raise AuthError("Invalid email or password.") from exc
    with _connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE email=? AND auth_provider='email'", (email,)).fetchone()
        if not row or not row["password_hash"] or not hmac.compare_digest(_password_hash(password, row["password_salt"]), row["password_hash"]):
            raise AuthError("Invalid email or password.")
        connection.execute("UPDATE users SET last_login_at=? WHERE user_id=?", (datetime.now(timezone.utc).isoformat(), row["user_id"]))
        return _row_user(row)


def upsert_oidc_user(email: str, display_name: str) -> AuthUser:
    email = _normalize_email(email)
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            connection.execute("UPDATE users SET last_login_at=?,display_name=? WHERE user_id=?", (now, display_name or row["display_name"], row["user_id"]))
            return AuthUser(row["user_id"], email, display_name or row["display_name"], row["auth_provider"])
        user_id = uuid4().hex
        connection.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?,?)", (user_id, email, display_name or email.split("@")[0], None, None, "google", now, now))
        return AuthUser(user_id, email, display_name or email.split("@")[0], "google")


def get_user(user_id: str) -> AuthUser | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return _row_user(row) if row else None


def record_import(user_id: str, filename: str, status: str, rows_loaded: int, manifest_json: str, error_message: str | None = None) -> None:
    with _connect() as connection:
        connection.execute("INSERT INTO data_imports VALUES(?,?,?,?,?,?,?,?)", (
            uuid4().hex, user_id, filename, status, rows_loaded, manifest_json, error_message,
            datetime.now(timezone.utc).isoformat(),
        ))


def list_imports(user_id: str, limit: int = 10) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute("SELECT filename,status,rows_loaded,created_at,error_message FROM data_imports WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(row) for row in rows]
