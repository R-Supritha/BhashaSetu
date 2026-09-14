from flask import Blueprint, request, jsonify

from backend.services import speech_service
from backend.utils.security import require_auth

bp = Blueprint("speech", __name__, url_prefix="/api/speech")


@bp.post("/transcribe")
@require_auth
def transcribe():
    """
    Accepts either:
      - multipart/form-data with an 'audio' file, or
      - JSON {"demo_key": "teacher_default" | "student_doubt", "expected_language": "hi"}
        for the demo/no-microphone path.
    """
    demo_key = "teacher_default"
    expected_language = "hi"
    audio_bytes = None

    if request.files.get("audio"):
        audio_bytes = request.files["audio"].read()
        expected_language = request.form.get("expected_language", "hi")
        demo_key = request.form.get("demo_key", demo_key)
    else:
        body = request.get_json(silent=True) or {}
        expected_language = body.get("expected_language", expected_language)
        demo_key = body.get("demo_key", demo_key)

    result = speech_service.transcribe(audio_bytes, expected_language, demo_key)
    return jsonify(result)
