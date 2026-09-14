from flask import Blueprint, request, jsonify

from backend.services import speech_service, language_service, translation_service, rag_service, llm_service
from backend.utils.security import require_auth

bp = Blueprint("doubt", __name__, url_prefix="/api/doubt")


@bp.post("")
@require_auth
def handle_doubt():
    """
    Full doubt pipeline in one call, matching the spec's flow:
    Santhali speech -> Santhali text -> Hindi -> RAG -> LLM explanation.

    Accepts multipart audio (field 'audio') or JSON {"demo_key": "student_doubt"}
    for the no-microphone demo path.
    """
    demo_key = "student_doubt"
    audio_bytes = None
    if request.files.get("audio"):
        audio_bytes = request.files["audio"].read()
    else:
        body = request.get_json(silent=True) or {}
        demo_key = body.get("demo_key", demo_key)

    transcript = speech_service.transcribe(audio_bytes, expected_language="sat", demo_key=demo_key)
    santhali_text = transcript["text"]

    language = language_service.identify(santhali_text)

    hindi_translation = translation_service.translate(santhali_text, "sat", "hi")
    hindi_question = hindi_translation["translated_text"]

    retrieval = rag_service.retrieve(hindi_question, top_k=3)
    explanation = llm_service.explain_doubt(hindi_question, retrieval["chunks"])

    return jsonify({
        "santhali_question": santhali_text,
        "detected_language": language["language"],
        "hindi_question": hindi_question,
        "textbook_context": retrieval["chunks"],
        "explanation": explanation["answer"],
        "warnings": [w for w in [
            transcript.get("warning"),
            hindi_translation.get("warning"),
            retrieval.get("warning"),
            explanation.get("warning"),
        ] if w],
        "modes": {
            "speech": transcript["mode"],
            "translation": hindi_translation["mode"],
            "retrieval": retrieval["mode"],
            "llm": explanation["mode"],
            "llm_engine": explanation.get("engine") or "canned-explanation",
        },
    })
