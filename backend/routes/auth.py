from flask import Blueprint, request, jsonify, g

from backend.database import json_store
from backend.utils.security import verify_password, issue_token, revoke_token, require_auth

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    teacher_id = (body.get("teacher_id") or "").strip()
    password = body.get("password") or ""

    if not teacher_id or not password:
        return jsonify({"error": "bad_request", "message": "teacher_id and password are required."}), 400

    teacher = json_store.teachers.find_one({"teacher_id": teacher_id})
    if not teacher or not verify_password(password, teacher["password_hash"]):
        return jsonify({"error": "invalid_credentials", "message": "Incorrect teacher ID or password."}), 401

    token = issue_token(teacher["_id"])
    return jsonify({
        "token": token,
        "teacher": {
            "id": teacher["_id"],
            "name": teacher["name"],
            "class_name": teacher["class_name"],
            "subject": teacher["subject"],
        },
    })


@bp.post("/logout")
@require_auth
def logout():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1]
    revoke_token(token)
    return jsonify({"ok": True})


@bp.get("/me")
@require_auth
def me():
    teacher = json_store.teachers.find_by_id(g.teacher_id)
    return jsonify({
        "id": teacher["_id"],
        "name": teacher["name"],
        "class_name": teacher["class_name"],
        "subject": teacher["subject"],
    })
