"""
Populates the JSON store with enough demo data to run the full SIH walkthrough
immediately after `git clone` + `pip install` — no manual data entry needed.

Idempotent: every collection uses `seed_if_empty`, so re-running this (or just
restarting the app) never duplicates data. Delete a file under data/ if you
want it reseeded.
"""

import json
import random
from pathlib import Path

from backend.database import json_store
from backend.utils.security import hash_password

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_json(relative_path: str) -> list:
    with (DATA_DIR / relative_path).open("r", encoding="utf-8") as f:
        return json.load(f)


def seed_teachers() -> None:
    json_store.teachers.seed_if_empty([
        {
            "_id": "T-1001",
            "teacher_id": "T-1001",
            "name": "Mrs. Hembrom",
            "password_hash": hash_password("demo1234"),
            "class_name": "Class 3",
            "subject": "Environmental Studies",
        }
    ])


def seed_lessons() -> None:
    json_store.lessons.seed_if_empty([
        {
            "_id": "lesson-parts-of-a-plant",
            "title": "Parts of a Plant",
            "class_name": "Class 3",
            "subject": "Environmental Studies",
            "teacher_language": "hi",
            "student_language": "sat",
            "worksheet_id": "worksheet-parts-of-a-plant",
            "concepts": ["plant", "root", "stem", "leaf", "flower", "fruit", "seed", "water", "sunlight"],
        }
    ])


def seed_students() -> None:
    """
    Exact 30-student roster for the demo class (S-1000..S-1029) with stable IDs.
    Analytics derives students_total from this roster (not from submissions),
    so duplicate submissions can never inflate the class size.
    """
    roster = [
        {
            "_id": f"S-{1000 + i}",
            "student_id": f"S-{1000 + i}",
            "full_name": f"Student {i + 1:02d}",
            "class_name": "Class 3",
            "language": "sat",
        }
        for i in range(30)
    ]
    json_store.students.seed_if_empty(roster)


def seed_flashcards() -> None:
    json_store.flashcards.seed_if_empty(_load_json("flashcards/seed.json"))


def seed_worksheets() -> None:
    json_store.worksheets.seed_if_empty(_load_json("worksheets/seed.json"))


def seed_sample_submissions(class_size: int = 30, completed: int = 27) -> None:
    """
    Realistic-looking Class 3 submissions for 'Parts of a Plant', with
    'flower' deliberately weak (~60% mastery) so the Assessment & Analytics
    screen has a concept worth flagging for remediation right out of the box.
    """
    if json_store.worksheet_submissions.count({"worksheet_id": "worksheet-parts-of-a-plant"}):
        return  # already seeded

    worksheet = json_store.worksheets.find_by_id("worksheet-parts-of-a-plant")
    if not worksheet:
        return

    # Per-concept target accuracy, tuned so the class average lands near 78%
    # and "flower" is the standout weak concept, matching the doc's example.
    accuracy_by_concept = {
        "root": 0.85,
        "stem": 0.72,
        "leaf": 0.90,
        "flower": 0.61,
        "fruit": 0.80,
    }

    rng = random.Random(42)  # deterministic demo data
    for student_index in range(completed):
        student_id = f"S-{1000 + student_index}"
        answers = {}
        for question in worksheet["questions"]:
            target_accuracy = accuracy_by_concept.get(question["concept"], 0.75)
            is_correct = rng.random() < target_accuracy
            if is_correct:
                answers[question["id"]] = question["correct_option"]
            else:
                wrong_options = [o for o in question["options"] if o != question["correct_option"]]
                answers[question["id"]] = rng.choice(wrong_options)

        # Insert directly (bypassing worksheet_service so we can backdate
        # deterministically) but reuse its scoring logic for consistency.
        from backend.services.worksheet_service import _score_submission
        correct_count, total_count, concept_results = _score_submission(worksheet, answers)
        json_store.worksheet_submissions.insert_one({
            "worksheet_id": "worksheet-parts-of-a-plant",
            "student_id": student_id,
            "answers": answers,
            "score_percent": round((correct_count / total_count) * 100),
            "correct_count": correct_count,
            "total_count": total_count,
            "concept_results": concept_results,
            "attempts": 1,
            "submitted_at": "2026-09-01T09:00:00+00:00",
        })


def seed_all() -> None:
    seed_teachers()
    seed_students()
    seed_lessons()
    seed_flashcards()
    seed_worksheets()
    seed_sample_submissions()


if __name__ == "__main__":
    seed_all()
    print("Seed complete.")
