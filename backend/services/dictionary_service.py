"""
Dictionary service: a deterministic, read-only word list (Hindi / Santali Ol
Chiki / English) built exclusively from stored app data (the translation
glossary and lesson vocabulary). It never asks Qwen or any LLM to produce
translations — every entry is pre-seeded and label-checked.
"""

import json
from pathlib import Path

_DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "dictionary" / "seed.json"

_cache: list[dict] | None = None


_LANGUAGE_FIELDS = {
    "hi": "hindi",
    "hindi": "hindi",
    "sat": "santali_ol_chiki",
    "santali": "santali_ol_chiki",
    "santali_ol_chiki": "santali_ol_chiki",
    "olchiki": "santali_ol_chiki",
    "en": "english",
    "english": "english",
}

SOURCE_ALIAS = {
    "hi": "hindi",
    "hindi": "hindi",
    "sat": "santali_ol_chiki",
    "santali": "santali_ol_chiki",
    "santhali": "santali_ol_chiki",
    "ol-chiki": "santali_ol_chiki",
    "olchiki": "santali_ol_chiki",
    "en": "english",
    "english": "english",
}


def _load() -> list[dict]:
    global _cache
    if _cache is None:
        if _DATA_FILE.exists():
            with _DATA_FILE.open("r", encoding="utf-8") as f:
                _cache = json.load(f)
        else:
            _cache = []
    return _cache


def _canonical_language(lang: str | None) -> str | None:
    if not lang:
        return None
    key = str(lang).strip().lower()
    return SOURCE_ALIAS.get(key)


def list_entries(query: str | None = None, source_language: str | None = None, target_language: str | None = None) -> list[dict]:
    """All dictionary entries, optionally filtered by dictionary search terms and an
    optional source→target language direction.

    Stored data only: Hindi, English and Santali Ol Chiki vocabulary are matched
    against the existing JSON dictionary. When a source and target language are
    supplied, we search the stored source field and preserve the dictionary entry
    as a static lookup, never inventing or auto-generating a translation.
    """
    entries = _load()
    query = (query or "").strip()
    source_field = _canonical_language(source_language)
    target_field = _canonical_language(target_language)

    if not query:
        return entries

    needle = query.lower()
    if not needle:
        return entries

    matched = []
    for entry in entries:
        # Support client-supplied direction semantics: Hindi→Santali and Santali→Hindi
        # should search only in the source language field from the stored vocabulary.
        if source_field and target_field:
            source_value = str(entry.get(source_field) or "").lower()
            if needle in source_value:
                matched.append(entry)
            continue

        # Cross-store fallback: if the user enters a word/string without a direction,
        # search the deterministic searchable columns exactly as the UI already expects.
        haystack = " ".join([
            entry.get("hindi") or "",
            entry.get("english") or "",
            entry.get("santali_ol_chiki") or "",
            entry.get("pronunciation") or "",
            entry.get("meaning") or "",
        ]).lower()
        if needle in haystack:
            matched.append(entry)
    return matched


def get_entry(entry_id: str) -> dict | None:
    for entry in _load():
        if entry.get("id") == entry_id:
            return entry
    return None