from flask import Blueprint, request, jsonify

from backend.services import flashcard_service
from backend.utils.security import require_auth

bp = Blueprint("flashcards", __name__, url_prefix="/api/flashcards")


@bp.get("")
@require_auth
def list_flashcards():
    lesson = request.args.get("lesson")
    return jsonify(flashcard_service.list_all(lesson))


@bp.get("/<flashcard_id>")
@require_auth
def get_flashcard(flashcard_id):
    card = flashcard_service.get_by_id(flashcard_id)
    if not card:
        return jsonify({"error": "not_found"}), 404
    return jsonify(card)


@bp.post("/retrieve")
@require_auth
def retrieve_flashcard():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "")
    card = flashcard_service.retrieve_for_text(text)
    return jsonify(card or {})
