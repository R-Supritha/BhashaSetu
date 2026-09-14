"""
Worksheet lifecycle: teacher assigns -> student submits -> score + concept
mapping stored for the analytics service to aggregate later.
"""

import re
import uuid
from datetime import datetime, timezone

from backend.database import json_store
from backend.config import Config
from backend.services import llm_service


def list_worksheets() -> list[dict]:
    return json_store.worksheets.all()


def get_worksheet(worksheet_id: str) -> dict | None:
    return json_store.worksheets.find_by_id(worksheet_id)


def assign_worksheet(worksheet_id: str, class_name: str) -> dict:
    return json_store.worksheet_assignments.insert_one({
        "worksheet_id": worksheet_id,
        "class_name": class_name,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
    })


def create_worksheet_from_quiz(quiz: dict, topic: str, lesson: str = "", subject: str = "") -> dict:
    """
    Persist a generated quiz (Qwen or template) as a normal worksheet so it can
    flow through the existing assign -> submit -> analytics pipeline. The quiz
    shape (correct_answer) is normalised into the worksheet schema
    (correct_option/prompt/options/concept) without changing the content.
    """
    topic_label = (topic or "").strip() or "Lesson"
    source_slug = re.sub(r"[^a-z0-9]+", "-", topic_label.lower()).strip("-") or "lesson"
    worksheet_id = f"generated-{source_slug}-{uuid.uuid4().hex[:6]}"
    existing = json_store.worksheets.find_by_id(worksheet_id)
    if existing:
        return existing

    questions = []
    for q in quiz.get("questions") or []:
        qid = q.get("id") or q.get("qid") or f"g{len(questions) + 1}"
        correct = q.get("correct_option") or q.get("correct_answer")
        questions.append({
            "id": str(qid),
            "type": q.get("type") or "mcq",
            "prompt": q.get("prompt") or q.get("question") or "",
            "options": q.get("options") or [],
            "correct_option": str(correct or "").strip(),
            "concept": (q.get("concept") or "").strip() or "plant",
            "difficulty": q.get("difficulty") or "medium",
        })

    worksheet = {
        "_id": worksheet_id,
        "title": f"{topic_label.title()} — Worksheet",
        "class_name": "Class 3",
        "subject": subject or "Environmental Studies",
        "lesson_id": lesson or "lesson-parts-of-a-plant",
        "questions": questions,
        "generated": True,
    }
    json_store.worksheets.insert_one(worksheet)
    return worksheet


def _score_submission(worksheet: dict, answers: dict) -> tuple[int, int, dict]:
    """
    Returns (correct_count, total_count, concept_results) where
    concept_results maps concept -> "correct"/"incorrect" per question.
    """
    correct_count = 0
    concept_results: dict[str, str] = {}
    for question in worksheet["questions"]:
        qid = question["id"]
        given = answers.get(qid)
        is_correct = given is not None and given == question["correct_option"]
        if is_correct:
            correct_count += 1
        concept_results[question["concept"]] = "correct" if is_correct else "incorrect"
    return correct_count, len(worksheet["questions"]), concept_results


def submit_worksheet(worksheet_id: str, student_id: str, answers: dict, explanations: dict | None = None) -> dict:
    worksheet = get_worksheet(worksheet_id)
    if not worksheet:
        raise ValueError(f"Unknown worksheet_id: {worksheet_id}")

    # Deterministic objective scoring first — the LLM never changes this.
    correct_count, total_count, concept_results = _score_submission(worksheet, answers)
    score_percent = round((correct_count / total_count) * 100) if total_count else 0

    # Additive, optional: analyse free-text "student's own explanation" only
    # where one was actually supplied. Purely diagnostic — no score impact.
    llm_analysis: dict[str, dict] = {}
    for qid, text in (explanations or {}).items():
        if not text or not str(text).strip():
            continue
        question = next((q for q in worksheet["questions"] if q["id"] == qid), None)
        if not question:
            continue
        llm_analysis[qid] = llm_service.analyze_misconception(
            question=question.get("prompt", ""),
            expected_answer=str(question.get("correct_option") or ""),
            student_answer=str(answers.get(qid) or ""),
            student_explanation=str(text),
            concept=question.get("concept", ""),
        )

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "worksheet_id": worksheet_id,
        "student_id": student_id,
        "answers": answers,
        "score_percent": score_percent,
        "correct_count": correct_count,
        "total_count": total_count,
        "concept_results": concept_results,
        "llm_analysis": llm_analysis or None,
        "submitted_at": now,
    }

    # Re-submission semantics: update the student's latest submission in place
    # (keeping one record per student) and count the attempt. Duplicate rows are
    # never created, so analytics student counts can't be inflated.
    existing = json_store.worksheet_submissions.find_one({
        "worksheet_id": worksheet_id,
        "student_id": student_id,
    })
    if existing:
        attempts = int(existing.get("attempts") or 1) + 1
        return json_store.worksheet_submissions.update_one(
            {"worksheet_id": worksheet_id, "student_id": student_id},
            {**payload, "attempts": attempts},
        )

    return json_store.worksheet_submissions.insert_one({**payload, "attempts": 1})
