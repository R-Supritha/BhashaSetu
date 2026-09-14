from flask import Blueprint, request, jsonify

from backend.database import json_store
from backend.services import assessment_service, personalization_service
from backend.utils.security import require_auth

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@bp.get("/submissions")
@require_auth
def submissions():
    worksheet_id = request.args.get("worksheet_id")
    query = {"worksheet_id": worksheet_id} if worksheet_id else None
    rows = json_store.worksheet_submissions.find(query)
    rows = sorted(rows, key=lambda s: s.get("submitted_at") or "", reverse=True)
    return jsonify([{
        "student_id": row["student_id"],
        "score_percent": row["score_percent"],
        "correct_count": row["correct_count"],
        "total_count": row["total_count"],
        "concept_results": row["concept_results"],
        "submitted_at": row.get("submitted_at"),
    } for row in rows])


@bp.get("")
@require_auth
def full_report():
    worksheet_id = request.args.get("worksheet_id")
    class_size = request.args.get("class_size", type=int)
    return jsonify(assessment_service.full_report(worksheet_id, class_size))


@bp.get("/concepts")
@require_auth
def concept_mastery():
    worksheet_id = request.args.get("worksheet_id")
    return jsonify(assessment_service.concept_mastery(worksheet_id))


@bp.get("/recommendations")
@require_auth
def recommendations():
    worksheet_id = request.args.get("worksheet_id")
    return jsonify(personalization_service.recommendations_for(worksheet_id))
