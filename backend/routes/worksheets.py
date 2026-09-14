from flask import Blueprint, request, jsonify

from backend.services import worksheet_service, llm_service, rag_service, evaluation_service
from backend.utils.security import require_auth

bp = Blueprint("worksheets", __name__, url_prefix="/api/worksheets")


@bp.get("")
@require_auth
def list_worksheets():
    return jsonify(worksheet_service.list_worksheets())


@bp.get("/<worksheet_id>")
def get_worksheet(worksheet_id):
    # Intentionally NOT behind @require_auth — students use their own devices
    # without a teacher login for this prototype.
    worksheet = worksheet_service.get_worksheet(worksheet_id)
    if not worksheet:
        return jsonify({"error": "not_found"}), 404
    return jsonify(worksheet)


@bp.post("/assign")
@require_auth
def assign_worksheet():
    body = request.get_json(silent=True) or {}
    worksheet_id = body.get("worksheet_id")
    class_name = body.get("class_name")
    if not worksheet_id or not class_name:
        return jsonify({"error": "bad_request", "message": "worksheet_id and class_name are required."}), 400

    assignment = worksheet_service.assign_worksheet(worksheet_id, class_name)
    return jsonify(assignment), 201


@bp.post("/generate")
@require_auth
def generate_quiz():
    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or body.get("prompt") or "plant").strip()
    grade_level = int(body.get("grade_level") or 3)
    difficulty = (body.get("difficulty") or "medium").strip()
    lesson = (body.get("lesson") or "").strip()
    subject = (body.get("subject") or "").strip()

    context = []
    if lesson or subject or topic:
        try:
            retrieval = rag_service.retrieve(topic, top_k=3, lesson=lesson or None, subject=subject or None)
            context = retrieval.get("chunks") or []
        except Exception:
            context = []

    quiz = llm_service.generate_quiz(topic, grade_level, difficulty, context)
    worksheet = worksheet_service.create_worksheet_from_quiz(quiz, topic, lesson, subject)
    return jsonify({
        "worksheet_id": worksheet["_id"],
        "title": worksheet["title"],
        "grade_level": grade_level,
        "subject": subject,
        "lesson": lesson,
        "questions": worksheet["questions"],
        "mode": quiz["mode"],
        "engine": quiz["engine"],
        "warning": quiz.get("warning"),
    })


@bp.post("/evaluate")
@require_auth
def evaluate_answer():
    body = request.get_json(silent=True) or {}
    question = body.get("question") or {}
    student_answer = (body.get("student_answer") or "").strip()
    if not question:
        return jsonify({"error": "bad_request", "message": "question is required."}), 400
    if not isinstance(student_answer, str):
        return jsonify({"error": "bad_request", "message": "student_answer must be a string."}), 400

    result = evaluation_service.evaluate_answer(question, student_answer)
    return jsonify(result)


@bp.post("/submit")
def submit_worksheet():
    # Also not behind @require_auth — this is the student-facing endpoint.
    body = request.get_json(silent=True) or {}
    worksheet_id = body.get("worksheet_id")
    student_id = body.get("student_id")
    answers = body.get("answers")

    if not worksheet_id or not student_id or not isinstance(answers, dict):
        return jsonify({
            "error": "bad_request",
            "message": "worksheet_id, student_id, and answers (object) are required.",
        }), 400

    try:
        submission = worksheet_service.submit_worksheet(
            worksheet_id, student_id, answers, body.get("explanations"),
        )
    except ValueError as exc:
        return jsonify({"error": "not_found", "message": str(exc)}), 404

    return jsonify(submission), 201


@bp.post("/misconception")
@require_auth
def analyze_misconception():
    """
    Misconception Detector: classify why a child's answer differs from the
    expected one. Inputs (all strings/dicts) come from the caller; the
    classification is produced by the local Qwen model when available,
    otherwise by a clearly-labelled heuristic.
    """
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "bad_request", "message": "question is required."}), 400

    result = llm_service.analyze_misconception(
        question=question,
        expected_answer=(body.get("expected_answer") or "").strip(),
        student_answer=(body.get("student_answer") or "").strip(),
        student_explanation=(body.get("student_explanation") or "").strip(),
        concept=(body.get("concept") or "").strip(),
        class_stats=body.get("class_stats") or None,
    )
    return jsonify(result)
