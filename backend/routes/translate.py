from flask import Blueprint, request, jsonify

from backend.services import translation_service, flashcard_service
from backend.utils.security import require_auth

bp = Blueprint("translate", __name__, url_prefix="/api/translate")


@bp.post("")
@require_auth
def translate():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    source_language = body.get("source_language", "hi")
    target_language = body.get("target_language", "sat")

    if not text:
        return jsonify({"error": "bad_request", "message": "text is required."}), 400

    result = translation_service.translate(text, source_language, target_language)

    # Bundle the relevant flashcard so the Live Classroom / projector view can
    # render translation + flashcard in one round trip.
    flashcard = flashcard_service.retrieve_for_text(text) or flashcard_service.retrieve_for_text(
        result["translated_text"]
    )
    result["flashcard"] = flashcard
    return jsonify(result)
