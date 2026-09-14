from flask import Blueprint, request, jsonify

from backend.services import dictionary_service

bp = Blueprint("dictionary", __name__, url_prefix="/api/dictionary")


@bp.get("")
def list_dictionary():
    """Read-only, deterministic dictionary lookup (stored data only).

    Public by design: it is a reference used by teachers and students alike,
    never invokes the LLM, and contains no sensitive information.

    Supports a stored-data translation-style search by accepting source and
    target language fields while remaining pure dictionary retrieval.
    """
    query = request.args.get("query") or request.args.get("q") or None
    source = request.args.get("source") or request.args.get("from_language") or None
    target = request.args.get("target") or request.args.get("to_language") or None
    return jsonify(dictionary_service.list_entries(query, source, target))


@bp.get("/<entry_id>")
def get_entry(entry_id):
    entry = dictionary_service.get_entry(entry_id)
    if not entry:
        return jsonify({"error": "not_found"}), 404
    return jsonify(entry)