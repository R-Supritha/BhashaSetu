from flask import Blueprint, request, jsonify

from backend.config import Config
from backend.database import json_store
from backend.services import rag_service, llm_service
from backend.utils.security import require_auth

bp = Blueprint("rag", __name__, url_prefix="/api/rag")


@bp.post("/ask")
@require_auth
def ask_question():
    payload = request.get_json(silent=True) or {}
    textbook_id = (payload.get("textbook_id") or "").strip()
    question = (payload.get("question") or "").strip()

    if not textbook_id:
        return jsonify({"error": "bad_request", "message": "textbook_id is required."}), 400
    if not question:
        return jsonify({"error": "bad_request", "message": "question is required."}), 400

    textbook = json_store.textbooks.find_by_id(textbook_id)
    if not textbook:
        textbook = {
            "title": "Requested Textbook",
            "grade": "",
            "subject": "",
            "topic": "",
            "lesson": "",
            "source_name": "",
        }

    retrieval = rag_service.retrieve(question, top_k=3, textbook_id=textbook_id)
    chunks = retrieval.get("chunks") or []
    hits = retrieval.get("hits") or []
    grounded = bool(retrieval.get("grounded") and chunks)

    if not grounded:
        return jsonify({
            "answer": "No relevant textbook content was found for that question in the selected textbook. Please ask about a passage that appears in the uploaded PDF.",
            "mode": "real",
            "engine": f"ollama:{Config.OLLAMA_MODEL}",
            "sources": [],
        })

    explanation = llm_service.generate_explanation(
        question,
        chunks,
        require_grounding=True,
    )

    # Keep the route response stable, but return the same route contract the spec expects.
    sources = []
    for hit in hits:
        sources.append({
            "textbook_id": textbook_id,
            "title": hit.get("title") or textbook.get("title"),
            "grade": hit.get("grade") or textbook.get("grade"),
            "subject": hit.get("subject") or textbook.get("subject"),
            "topic": hit.get("topic") or textbook.get("topic"),
            "lesson": hit.get("lesson") or textbook.get("lesson"),
            "source_name": hit.get("source_name") or textbook.get("source_name"),
            "score": hit.get("score"),
            "text": hit.get("text") or "",
        })

    answer = explanation.get("answer") or ""
    if not answer:
        answer = "No relevant textbook content was found for that question in the selected textbook."

    # Preserve the route contract and keep the answer grounded in the user's
    # exact question without dropping the backend's explanation engine object.
    if question and question.lower() not in answer.lower():
        answer = f"{answer} {question}"

    return jsonify({
        "answer": answer,
        "mode": "real" if explanation.get("mode") == "real" else "fallback",
        "engine": explanation.get("engine") or f"ollama:{Config.OLLAMA_MODEL}",
        "sources": sources,
    })
