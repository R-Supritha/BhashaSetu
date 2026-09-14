"""
Flashcards are pre-stored (never LLM-generated live, per the project spec).
This service just does lookup/retrieval against backend/database's flashcards
collection, which gets seeded from data/flashcards/seed.json on first run.
"""

from backend.database import json_store


def list_all(lesson: str | None = None) -> list[dict]:
    query = {"lesson": lesson} if lesson else None
    return json_store.flashcards.find(query)


def get_by_id(flashcard_id: str) -> dict | None:
    return json_store.flashcards.find_by_id(flashcard_id)


def get_by_concept(concept: str) -> dict | None:
    return json_store.flashcards.find_one({"concept": concept.strip().lower()})


def retrieve_for_text(text: str) -> dict | None:
    """
    Very deliberately simple keyword match: look for any flashcard's concept
    name appearing in the given transcript/translation text. This mirrors
    "retrieve the relevant flashcard based on the current lesson/concept/
    transcript" from the spec without needing an LLM call for something that
    should be fast and deterministic in a live classroom.
    """
    text_lower = text.lower()
    for card in json_store.flashcards.all():
        if card["concept"] in text_lower:
            return card
    return None
