"""
Curriculum RAG.

Uses the JSON store as the chunk index (always). Optional ChromaDB is tried
only in real mode if the package is installed — failure falls back to the
local TF-IDF/overlap index and is labelled.
"""

import math
import re
from collections import Counter
from datetime import datetime, timezone

from backend.config import Config
from backend.database import json_store
from backend.services import ocr_service


def _store_chroma(doc_id: str, text: str, title: str, grade: str, subject: str,
                   topic: str, lesson: str, source_name: str, ordinal: int) -> None:
    try:
        import chromadb  # type: ignore
    except ImportError:
        return

    try:
        client = chromadb.PersistentClient(path=str(Config.CHROMA_PERSIST_DIR))
        collection = client.get_or_create_collection("bhashasetu_curriculum")
        collection.add(
            documents=[text],
            metadatas=[{
                "document_id": doc_id,
                "textbook_id": doc_id,
                "title": title,
                "grade": grade,
                "subject": subject,
                "topic": topic,
                "lesson": lesson,
                "source_name": source_name,
                "ordinal": ordinal,
            }],
            ids=[f"{doc_id}-{ordinal}"],
        )
    except Exception:
        # Chroma is optional: if the package is installed but the local DB is
        # not writable, the JSON curriculum index remains the source of truth.
        pass

_TOKEN = re.compile(r"[A-Za-z\u0900-\u097F\u1C50-\u1C7F]+")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


def _tfidf_score(query: str, chunk: str) -> float:
    q = _tokens(query)
    d = _tokens(chunk)
    if not q or not d:
        return 0.0
    qc, dc = Counter(q), Counter(d)
    overlap = set(qc) & set(dc)
    if not overlap:
        return 0.0
    dot = sum(qc[t] * dc[t] for t in overlap)
    qn = math.sqrt(sum(v * v for v in qc.values())) or 1.0
    dn = math.sqrt(sum(v * v for v in dc.values())) or 1.0
    return dot / (qn * dn)


def _chroma_retrieve(query: str, top_k: int, filters: dict) -> list[dict] | None:
    try:
        import chromadb  # type: ignore
    except ImportError:
        return None
    client = chromadb.PersistentClient(path=str(Config.CHROMA_PERSIST_DIR))
    collection = client.get_or_create_collection("bhashasetu_curriculum")
    where = {k: v for k, v in filters.items() if v} or None
    result = collection.query(query_texts=[query], n_results=top_k, where=where)
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]
    out = []
    for i, doc in enumerate(docs):
        out.append({
            "text": doc,
            "metadata": metas[i] if i < len(metas) else {},
            "score": 1.0 - float(dists[i]) if i < len(dists) else 0.0,
        })
    return out


def index_text(
    text: str,
    *,
    title: str,
    grade: str = "",
    subject: str = "",
    topic: str = "",
    lesson: str = "",
    source_name: str = "",
) -> dict:
    chunks = ocr_service.chunk_text(text)
    if not chunks:
        raise ValueError("No text chunks to index.")

    doc = json_store.textbooks.insert_one({
        "title": title,
        "grade": grade,
        "subject": subject,
        "topic": topic,
        "lesson": lesson,
        "source_name": source_name,
        "chunk_count": len(chunks),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    })
    stored = []
    for i, chunk in enumerate(chunks):
        row = json_store.curriculum_chunks.insert_one({
            "document_id": doc["_id"],
            "title": title,
            "grade": grade,
            "subject": subject,
            "topic": topic,
            "lesson": lesson,
            "source_name": source_name,
            "ordinal": i,
            "text": chunk,
        })
        stored.append(row)
        _store_chroma(doc["_id"], chunk, title, grade, subject, topic, lesson, source_name, i)
    return {"document": doc, "chunks_indexed": len(stored)}


def retrieve(query: str, top_k: int = 3, lesson: str | None = None,
             grade: str | None = None, subject: str | None = None,
             textbook_id: str | None = None) -> dict:
    filters = {"lesson": lesson, "grade": grade, "subject": subject}

    if not Config.is_demo():
        try:
            chroma_hits = _chroma_retrieve(query, top_k, filters)
            if chroma_hits:
                if textbook_id:
                    # Keep the textbook-specific ID grounded in the returned metadata.
                    chroma_hits = [h for h in chroma_hits if h.get("metadata", {}).get("textbook_id") == textbook_id]
                if chroma_hits:
                    return {
                        "mode": "real",
                        "engine": "chromadb",
                        "chunks": [h["text"] for h in chroma_hits],
                        "hits": chroma_hits,
                        "grounded": bool(chroma_hits),
                        "warning": None,
                    }
        except Exception:
            pass

    rows = json_store.curriculum_chunks.all()
    if textbook_id:
        rows = [r for r in rows if r.get("document_id") == textbook_id]
    if lesson:
        rows = [r for r in rows if r.get("lesson") == lesson]
    if grade:
        rows = [r for r in rows if r.get("grade") == grade]
    if subject:
        rows = [r for r in rows if r.get("subject") == subject]

    scored = []
    for row in rows:
        score = _tfidf_score(query, row.get("text", ""))
        if score >= Config.RAG_MIN_SCORE:
            row_meta = {
                **row,
                "document_id": row.get("document_id"),
                "title": row.get("title"),
                "grade": row.get("grade"),
                "subject": row.get("subject"),
                "topic": row.get("topic"),
                "lesson": row.get("lesson"),
                "source_name": row.get("source_name"),
                "score": round(score, 3),
            }
            scored.append(row_meta)
    scored.sort(key=lambda r: r["score"], reverse=True)
    hits = scored[:top_k]

    if not hits:
        return {
            "mode": "local-index",
            "engine": "overlap-tfidf",
            "chunks": [],
            "hits": [],
            "grounded": False,
            "warning": "Curriculum grounding unavailable — no indexed passage matched this question.",
        }

    return {
        "mode": "local-index",
        "engine": "overlap-tfidf",
        "chunks": [h["text"] for h in hits],
        "hits": [{
            "text": h["text"],
            "score": h["score"],
            "lesson": h.get("lesson"),
            "topic": h.get("topic"),
            "grade": h.get("grade"),
            "subject": h.get("subject"),
            "title": h.get("title"),
            "source_name": h.get("source_name"),
            "document_id": h.get("document_id"),
            "textbook_id": textbook_id,
        } for h in hits],
        "grounded": True,
        "warning": None,
    }
