"""
Small, deliberately un-fancy auth helpers for the prototype.

- Passwords are hashed with Werkzeug's PBKDF2 helper (never stored plain).
- "Sessions" are opaque bearer tokens kept in an in-memory dict mapping
  token -> teacher_id, with an expiry. This is enough for a single-process
  hackathon demo. If you need multi-process/restart-safe sessions later,
  swap _SESSIONS for a JsonCollection("sessions") — the functions below are
  the only thing that would need to change.
"""

import time
import uuid
from functools import wraps

from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 hours — long enough for a school day

_SESSIONS: dict[str, dict] = {}


def hash_password(plain_password: str) -> str:
    return generate_password_hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, plain_password)


def issue_token(teacher_id: str) -> str:
    token = uuid.uuid4().hex
    _SESSIONS[token] = {"teacher_id": teacher_id, "expires_at": time.time() + SESSION_TTL_SECONDS}
    return token


def revoke_token(token: str) -> None:
    _SESSIONS.pop(token, None)


def resolve_token(token: str) -> str | None:
    """Return the teacher_id for a valid, non-expired token, else None."""
    session = _SESSIONS.get(token)
    if not session:
        return None
    if session["expires_at"] < time.time():
        _SESSIONS.pop(token, None)
        return None
    return session["teacher_id"]


def require_auth(view_func):
    """Route decorator: rejects the request unless a valid Bearer token is present."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else None
        teacher_id = resolve_token(token) if token else None
        if not teacher_id:
            return jsonify({"error": "unauthorized", "message": "Login required."}), 401
        g.teacher_id = teacher_id
        return view_func(*args, **kwargs)

    return wrapped
