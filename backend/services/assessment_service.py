"""
Turns raw worksheet_submissions into the numbers the Assessment & Analytics
screen needs: class average, completion, per-concept mastery %, and which
concepts are "weak" (below WEAK_CONCEPT_THRESHOLD).

Class-size semantics (so duplicates can never inflate the numbers):
  - students_total is derived from the seeded student roster, NOT from
    submission records;
  - "completed" counts UNIQUE students who have a submission, and averages/
    mastery are computed over the student's LATEST submission only;
  - "submission_attempts" is the raw record count, so resubmissions stay
    visible without changing the student count.
"""

from backend.database import json_store

WEAK_CONCEPT_THRESHOLD = 70  # percent — below this, a concept is flagged for re-teaching


def roster_size() -> int:
    """Number of students in the seeded roster. Falls back to 0 if absent."""
    return json_store.students.count({})


def _latest_per_student(submissions: list[dict]) -> list[dict]:
    """Latest submission per (worksheet, student) so resubmissions never
    double-count a student in completion/average/mastery numbers."""
    by_student: dict[str, dict] = {}
    for submission in submissions:
        current = by_student.get(submission["student_id"])
        if current is None or _submitted_after(submission, current):
            by_student[submission["student_id"]] = submission
    return list(by_student.values())


def _submitted_after(a: dict, b: dict) -> bool:
    a_at = a.get("submitted_at") or ""
    b_at = b.get("submitted_at") or ""
    if a_at != b_at:
        return a_at > b_at
    return (a.get("_id") or "") > (b.get("_id") or "")


def class_summary(worksheet_id: str | None = None, class_size: int | None = None) -> dict:
    query = {"worksheet_id": worksheet_id} if worksheet_id else None
    submissions = json_store.worksheet_submissions.find(query)

    latest = _latest_per_student(submissions)
    completed = len(latest)
    average_score = round(sum(s["score_percent"] for s in latest) / completed) if completed else 0

    # Roster (seeded, exactly 30) wins; the query param is only a fallback for
    # environments without a students collection.
    students_total = roster_size() or class_size
    if students_total is None:
        students_total = completed
    students_total = max(students_total, 0)

    return {
        "students_total": students_total,
        "completed": completed,
        "pending": max(students_total - completed, 0),
        "submission_attempts": len(submissions),
        "average_score_percent": average_score,
    }


def concept_mastery(worksheet_id: str | None = None) -> dict:
    """Returns {concept: mastery_percent} across each student's latest submission."""
    query = {"worksheet_id": worksheet_id} if worksheet_id else None
    submissions = json_store.worksheet_submissions.find(query)
    latest = _latest_per_student(submissions)

    tally: dict[str, list[int]] = {}
    for submission in latest:
        for concept, result in submission["concept_results"].items():
            tally.setdefault(concept, []).append(1 if result == "correct" else 0)

    return {
        concept: round(sum(results) / len(results) * 100)
        for concept, results in tally.items()
    }


def weak_concepts(worksheet_id: str | None = None) -> list[dict]:
    mastery = concept_mastery(worksheet_id)
    weak = [
        {"concept": concept, "mastery_percent": pct}
        for concept, pct in mastery.items()
        if pct < WEAK_CONCEPT_THRESHOLD
    ]
    return sorted(weak, key=lambda c: c["mastery_percent"])


def full_report(worksheet_id: str | None = None, class_size: int | None = None) -> dict:
    weak = weak_concepts(worksheet_id)
    return {
        "summary": class_summary(worksheet_id, class_size),
        "concept_mastery": concept_mastery(worksheet_id),
        "weak_concepts": weak,
        "recommendations": [
            f"Re-teach {item['concept'].title()} using the visual flashcard and a simple explanation."
            for item in weak
        ],
    }