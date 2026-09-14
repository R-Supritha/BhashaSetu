from flask import Blueprint, request, jsonify

from backend.database import json_store
from backend.services import ocr_service, rag_service
from backend.utils.security import require_auth

bp = Blueprint("textbooks", __name__, url_prefix="/api/textbooks")


@bp.get("")
@require_auth
def list_textbooks():
    return jsonify(json_store.textbooks.all())


@bp.get("/<textbook_id>")
@require_auth
def get_textbook(textbook_id):
    item = json_store.textbooks.find_by_id(textbook_id)
    if not item:
        return jsonify({"error": "not_found", "message": "Textbook not found."}), 404
    return jsonify(item)


@bp.post("/upload")
@require_auth
def upload_textbook():
    if "file" not in request.files:
        return jsonify({"error": "bad_request", "message": "file is required."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "bad_request", "message": "file is required."}), 400

    title = (request.form.get("title") or uploaded.filename).strip()
    grade = (request.form.get("grade") or "").strip()
    subject = (request.form.get("subject") or "").strip()
    topic = (request.form.get("topic") or "").strip()
    lesson = (request.form.get("lesson") or "").strip()

    missing = [name for name, value in {
        "grade": grade,
        "subject": subject,
        "topic": topic,
        "lesson": lesson,
    }.items() if not value]
    if missing:
        return jsonify({"error": "bad_request", "message": f"Missing fields: {', '.join(missing)}"}), 400

    data = uploaded.read()
    extracted = ocr_service.extract_from_bytes(data, uploaded.filename, uploaded.mimetype or "")
    if not extracted.get("ok"):
        return jsonify({
            "error": "ocr_failed",
            "message": extracted.get("warning") or "OCR failed to extract readable text.",
        }), 400

    try:
        result = rag_service.index_text(
            extracted["text"],
            title=title,
            grade=grade,
            subject=subject,
            topic=topic,
            lesson=lesson,
            source_name=uploaded.filename,
        )
    except ValueError as exc:
        return jsonify({"error": "index_failed", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "index_failed", "message": f"Curriculum indexing failed ({exc.__class__.__name__})."}), 500

    return jsonify({"ok": True, "document": result["document"], "chunks_indexed": result["chunks_indexed"]})
