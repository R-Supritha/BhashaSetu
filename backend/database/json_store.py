"""
Minimal JSON-file backed data store.

BhashaSetu doesn't need MongoDB for the prototype stage, but the rest of the
codebase (routes/services) is written against a small Mongo-shaped interface
(find / find_one / insert_one / update_one / delete_one) so that swapping in
real MongoDB later means changing this file only, not every call site.

Each "collection" is one JSON file under Config.DATA_DIR, containing a list
of documents. Every document gets a string "_id" if it doesn't have one.

This is intentionally simple: it reads the whole file, mutates the list in
memory, and writes it back. That's more than fine for a hackathon prototype
with a handful of users and no concurrent writers.
"""

import json
import uuid
import threading
from pathlib import Path

from backend.config import Config

_LOCK = threading.Lock()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _matches(doc: dict, query: dict) -> bool:
    if not query:
        return True
    for key, value in query.items():
        if doc.get(key) != value:
            return False
    return True


class JsonCollection:
    """A single JSON-file-backed collection, e.g. `teachers`, `worksheets`."""

    def __init__(self, name: str):
        self.name = name
        self.path: Path = Config.DATA_DIR / f"{name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    # -- low-level io ----------------------------------------------------
    def _read(self) -> list:
        with self.path.open("r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []

    def _write(self, docs: list) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)

    # -- mongo-ish interface ----------------------------------------------
    def all(self) -> list:
        with _LOCK:
            return self._read()

    def find(self, query: dict | None = None) -> list:
        with _LOCK:
            docs = self._read()
        return [d for d in docs if _matches(d, query or {})]

    def find_one(self, query: dict | None = None) -> dict | None:
        results = self.find(query)
        return results[0] if results else None

    def find_by_id(self, doc_id: str) -> dict | None:
        return self.find_one({"_id": doc_id})

    def insert_one(self, doc: dict) -> dict:
        doc = dict(doc)
        doc.setdefault("_id", _new_id())
        with _LOCK:
            docs = self._read()
            docs.append(doc)
            self._write(docs)
        return doc

    def insert_many(self, new_docs: list) -> list:
        inserted = []
        with _LOCK:
            docs = self._read()
            for doc in new_docs:
                doc = dict(doc)
                doc.setdefault("_id", _new_id())
                docs.append(doc)
                inserted.append(doc)
            self._write(docs)
        return inserted

    def update_one(self, query: dict, update: dict) -> dict | None:
        """`update` is a partial dict merged into the first matching doc."""
        with _LOCK:
            docs = self._read()
            for i, d in enumerate(docs):
                if _matches(d, query):
                    docs[i] = {**d, **update}
                    self._write(docs)
                    return docs[i]
        return None

    def delete_one(self, query: dict) -> bool:
        with _LOCK:
            docs = self._read()
            for i, d in enumerate(docs):
                if _matches(d, query):
                    docs.pop(i)
                    self._write(docs)
                    return True
        return False

    def count(self, query: dict | None = None) -> int:
        return len(self.find(query))

    def seed_if_empty(self, docs: list) -> None:
        """Populate with default/demo data the first time the app runs."""
        with _LOCK:
            existing = self._read()
            if existing:
                return
            seeded = []
            for doc in docs:
                doc = dict(doc)
                doc.setdefault("_id", _new_id())
                seeded.append(doc)
            self._write(seeded)


# Collections used across the app — mirrors the schema list in the SIH doc,
# minus anything Mongo-specific.
teachers = JsonCollection("teachers")
lessons = JsonCollection("lessons")
textbooks = JsonCollection("textbooks")
curriculum_chunks = JsonCollection("curriculum_chunks")
flashcards = JsonCollection("flashcards")
worksheets = JsonCollection("worksheets")
worksheet_assignments = JsonCollection("worksheet_assignments")
worksheet_submissions = JsonCollection("worksheet_submissions")
assessments = JsonCollection("assessments")
concept_mastery = JsonCollection("concept_mastery")
lesson_sessions = JsonCollection("lesson_sessions")
students = JsonCollection("students")
