from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from backend.database import json_store
from backend.utils.security import require_auth

bp = Blueprint("classroom", __name__, url_prefix="/api/classroom")


@bp.post("/start")
@require_auth
def start_classroom():
    """
    Records a live classroom session when the teacher starts a lesson from
    the Stitch lesson-setup screen. Pure bookkeeping on the existing
    lesson_sessions collection — all lesson data stays in the lessons store.
    """
    body = request.get_json(silent=True) or {}
    lesson_id = (body.get("lesson_id") or "").strip()
    lesson = json_store.lessons.find_by_id(lesson_id) if lesson_id else None

    session = json_store.lesson_sessions.insert_one({
        "lesson_id": lesson_id,
        "class_name": body.get("class_name") or (lesson or {}).get("class_name"),
        "subject": body.get("subject") or (lesson or {}).get("subject"),
        "teacher_language": body.get("teacher_language") or (lesson or {}).get("teacher_language") or "hi",
        "student_language": body.get("student_language") or (lesson or {}).get("student_language") or "sat",
        "worksheet_id": body.get("worksheet_id") or (lesson or {}).get("worksheet_id"),
        "concepts": body.get("concepts") or (lesson or {}).get("concepts", []),
        "status": "live",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    return jsonify(session), 201


@bp.get("/sessions")
@require_auth
def list_sessions():
    sessions = json_store.lesson_sessions.all()
    sessions.sort(key=lambda s: s.get("started_at") or "", reverse=True)
    return jsonify(sessions)