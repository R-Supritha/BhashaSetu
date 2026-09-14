from flask import Blueprint, request, jsonify

from backend.database import json_store
from backend.utils.security import require_auth

bp = Blueprint("lessons", __name__, url_prefix="/api/lessons")


@bp.get("")
@require_auth
def list_lessons():
    return jsonify(json_store.lessons.all())


@bp.post("")
@require_auth
def create_lesson():
    body = request.get_json(silent=True) or {}
    required = ["title", "class_name", "subject", "teacher_language", "student_language"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": "bad_request", "message": f"Missing fields: {', '.join(missing)}"}), 400

    lesson = json_store.lessons.insert_one({
        "title": body["title"],
        "class_name": body["class_name"],
        "subject": body["subject"],
        "teacher_language": body["teacher_language"],
        "student_language": body["student_language"],
        "worksheet_id": body.get("worksheet_id"),
        "concepts": body.get("concepts", []),
    })
    return jsonify(lesson), 201


@bp.get("/<lesson_id>")
@require_auth
def get_lesson(lesson_id):
    lesson = json_store.lessons.find_by_id(lesson_id)
    if not lesson:
        return jsonify({"error": "not_found"}), 404
    return jsonify(lesson)
