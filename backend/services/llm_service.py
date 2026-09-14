"""
Ollama + labelled fallbacks for every teacher/student-facing AI text task.

This module owns the prompt engineering and the REAL vs FALLBACK decision.
The raw HTTP conversation with the local daemon lives in ollama_service, so
this file never parses Ollama responses by hand or leaks connection details.

Rules honoured here:
  - never crash when the daemon is down or disabled;
  - never pretend a fallback is a live LLM (mode/engine always label it);
  - model name always comes from Config.OLLAMA_MODEL (the exact installed tag);
  - structured classifications are validated and clamped to known values;
  - nothing here changes deterministic scores or analytics numbers.
"""

from backend.config import Config
from backend.services import language_service, ollama_service

DEMO_EXPLANATIONS = {
    "default": (
        "Plants need sunlight to make their own food. They use sunlight, "
        "water, and air in their leaves. This is why plants grow best in bright places."
    ),
}

DEMO_QUIZ = [
    {
        "id": "gq1",
        "type": "mcq",
        "prompt": "Which part of the plant takes in water from the soil?",
        "options": ["Leaf", "Root", "Flower", "Fruit"],
        "correct_answer": "Root",
        "concept": "root",
        "difficulty": "easy",
    },
    {
        "id": "gq2",
        "type": "mcq",
        "prompt": "Which part helps the plant make food using sunlight?",
        "options": ["Root", "Stem", "Leaf", "Seed"],
        "correct_answer": "Leaf",
        "concept": "leaf",
        "difficulty": "easy",
    },
    {
        "id": "gq3",
        "type": "mcq",
        "prompt": "What do flowers help the plant make?",
        "options": ["Water", "Seeds", "Soil", "Sunlight"],
        "correct_answer": "Seeds",
        "concept": "flower",
        "difficulty": "medium",
    },
    {
        "id": "gq4",
        "type": "short",
        "prompt": "In one sentence, why do plants need sunlight?",
        "options": [],
        "correct_answer": "Plants use sunlight to make their own food.",
        "concept": "sunlight",
        "difficulty": "medium",
    },
]

# --- Focused prompts for primary education -------------------------------

MISCONCEPTION_CLASSIFIER_PROMPT = (
    "You are a kind primary-school teacher. A child answered a question.\n"
    "Classify ONLY what is wrong with this child's answer compared to the "
    "expected answer. Use ONLY the supplied question, expected answer, "
    "student answer, and student's own explanation. Never invent facts about "
    "the student and never explain your reasoning (no chain-of-thought).\n\n"
    "CRITICAL: judge the child's UNDERSTANDING, not their exact wording. "
    "If the child's answer conveys the same key idea as the expected answer, "
    "even with different words or only partly, classify it \"correct\".\n\n"
    "Classification must be exactly one of:\n"
    "  \"concept_gap\"  - the child understood the wording but has a wrong idea\n"
    "  \"language_gap\" - the child knows the idea but cannot express it in the "
    "expected language/script yet\n"
    "  \"context_gap\"  - we have too little information to classify\n"
    "  \"correct\"      - the answer matches the expected understanding\n\n"
    "Language hints:\n{language_hints}"
    "Rule: if the Student's answer is in a DIFFERENT language/script from the "
    "Expected answer and looks like a translation of the concept word, STRONGLY "
    "prefer \"language_gap\".\n\n"
    "Question: {question}\n"
    "Expected answer: {expected_answer}\n"
    "Student's answer: {student_answer}\n"
    "Student's own explanation: {student_explanation}\n"
    "Concept being tested: {concept}\n"
    "Optional class statistics: {class_stats}\n\n"
    'Reply with ONLY a valid JSON object shaped exactly like:\n'
    '{{"classification": "concept_gap", "reason": "a short plain reason", '
    '"confidence": 0.9, "suggested_action": "a concrete next step for the teacher"}}'
)


def _language_hints(student_answer: str, expected_answer: str) -> str:
    parts = []
    for label, text in (("Student answer", student_answer), ("Expected answer", expected_answer)):
        if not text or not str(text).strip():
            continue
        ident = language_service.identify(str(text))
        parts.append(f"{label} language/script: {ident['language']}")
    return ("\n".join(parts) + "\n") if parts else "(none supplied)\n"

ALTERNATE_EXPLANATION_PROMPT = (
    "You help a primary-school teacher. Many children share this misconception:\n"
    "{summary}\n"
    "Concept: {concept}\n\n"
    "Write ONE simple alternate explanation they have not heard yet. Rules:\n"
    "- plain words a grade {grade} child understands;\n"
    "- no jargon; use an everyday example when possible;\n"
    "- 2-4 short sentences, short enough to read aloud in class;\n"
    "- do not add textbook facts that are not about this concept.\n"
    "Answer:"
)

DOUBT_EXPLANATION_PROMPT = (
    "You help a primary-school teacher. Explain this student question in "
    "{language} for the teacher, simply and correctly:\n"
    "Question: {question}\n\n"
    "Use the textbook context below EXACTLY when it answers the question. "
    "If it does not contain the answer, say so plainly.\n"
    "Context:\n{context}\n\n"
    "Rules: 2-4 short sentences, plain words, grade {grade} level, correct "
    "{language} grammar, no invented words, no hallucinated facts, no "
    "reasoning shown. If an English word is clearer, use it.\nAnswer:"
)

WEAK_CONCEPT_INSIGHT_PROMPT = (
    "You help a primary-school teacher reviewing class results.\n"
    "Concept '{concept}' has only {mastery}% mastery. "
    "Additional class context: {context}\n\n"
    "In 2-3 simple sentences explain in plain language WHY this concept may "
    "be hard and what the teacher should re-teach first. Only use the given "
    "information; do not invent student details or data.\nAnswer:"
)


# --- Tiny deterministic fallbacks (always clearly labelled) ---------------

def _norm(text: str) -> str:
    return "".join(ch.lower() for ch in (text or "") if ch.isalnum() or ord(ch) > 127)


def _fallback_misconception(question, expected, student_answer, reason_warning) -> dict:
    student = _norm(student_answer)
    expected_norm = _norm(expected)
    if student == expected_norm or (student and expected_norm and student in expected_norm):
        classification, confidence, action = "correct", 0.65, "No action needed — answer matches the expected idea."
    elif not student:
        classification, confidence, action = "context_gap", 0.4, "Ask the child to answer again or rephrase."
    else:
        classification, confidence, action = "concept_gap", 0.45, "Re-teach the concept with a simple example."
    return {
        "mode": "fallback",
        "engine": "heuristic-classifier",
        "classification": classification,
        "reason": f"Labelled fallback: {reason_warning}",
        "confidence": confidence,
        "suggested_action": action,
        "warning": "Ollama did not produce a classifiable answer, so a labelled heuristic was used instead of a live LLM.",
    }


_ALLOWED_CLASSIFICATIONS = {"concept_gap", "language_gap", "context_gap", "correct"}


def _validate_classification(data: dict) -> dict | None:
    if not isinstance(data, dict):
        return None
    classification = data.get("classification") or ""
    if classification not in _ALLOWED_CLASSIFICATIONS:
        return None
    reason = str(data.get("reason") or "").strip() or "No reason provided."
    confidence = data.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = None
    if confidence is None:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    action = str(data.get("suggested_action") or "").strip() or "Re-teach the concept with a simple example."
    return {
        "classification": classification,
        "reason": reason,
        "confidence": confidence,
        "suggested_action": action,
    }


# --- Core handlers ---------------------------------------------------------

def ollama_status() -> dict:
    return ollama_service.is_available()


def _real_generate(prompt: str, *, temperature: float | None = None,
                   max_tokens: int | None = None) -> str | None:
    return ollama_service.chat(prompt, temperature=temperature, max_tokens=max_tokens)


def _normalized(text: str) -> str:
    return "".join(ch.lower() for ch in (text or "") if ch.isalnum() or ord(ch) > 127)


def _deterministic_precheck(expected_answer: str, student_answer: str) -> dict | None:
    """Bulletproof rules decided before any LLM call; never overridden by it.

    Returns a full result payload when a rule is decisive, else None.
    """
    student_norm = _normalized(student_answer)
    expected_norm = _normalized(expected_answer)

    if not student_norm:
        return {
            "mode": "fallback",
            "engine": "normalized-match",
            "classification": "context_gap",
            "reason": "No student answer was supplied to classify.",
            "confidence": 0.4,
            "suggested_action": "Ask the child to answer again or rephrase.",
            "warning": "Deterministic rule (empty answer), not an LLM judgment.",
        }

    if student_norm == expected_norm or (expected_norm and student_norm in expected_norm):
        return {
            "mode": "fallback",
            "engine": "normalized-match",
            "classification": "correct",
            "reason": "The student's answer matches the expected answer.",
            "confidence": 0.98,
            "suggested_action": "No action needed — the answer matches the expected idea.",
            "warning": "Deterministic exact match, not an LLM judgment.",
        }

    return None


def _language_gap_rule(expected_answer: str, student_answer: str) -> dict | None:
    """A short answer written in a clearly different language/script than the
    expected one is a language gap, whichever way the (small) model leans.
    Precise, cheap, and honest — the LLM still handles the content cases."""
    student, expected = str(student_answer), str(expected_answer)
    if not student or not expected:
        return None
    student_lang = language_service.identify(student)["language"]
    expected_lang = language_service.identify(expected)["language"]
    if student_lang not in ("hi", "sat", "en") or expected_lang not in ("hi", "sat", "en"):
        return None
    if student_lang == expected_lang:
        return None
    if len(student.split()) <= 4 and len(expected.split()) <= 4:
        return {
            "mode": "fallback",
            "engine": "script-language-rule",
            "classification": "language_gap",
            "reason": (
                f"The student wrote a short answer in {student_lang} while the "
                f"expected answer is in {expected_lang} — they know the word but "
                "still need support expressing it in the target language."
            ),
            "confidence": 0.9,
            "suggested_action": "Acknowledge the idea, model the target-language word, and ask the child to reuse it in a full sentence.",
            "warning": "Deterministic script/language rule, not an LLM judgment.",
        }
    return None


def analyze_misconception(
    question: str,
    expected_answer: str,
    student_answer: str,
    student_explanation: str = "",
    concept: str = "",
    class_stats: dict | None = None,
) -> dict:
    """Classify a child's answer gap via Qwen (real) or a labelled heuristic."""
    prechecked = _deterministic_precheck(expected_answer, student_answer)
    if prechecked is not None:
        return prechecked

    language_gap = _language_gap_rule(expected_answer, student_answer)
    if language_gap is not None:
        return language_gap

    prompt = MISCONCEPTION_CLASSIFIER_PROMPT.format(
        question=question or "(not supplied)",
        expected_answer=expected_answer or "(not supplied)",
        student_answer=student_answer or "(none)",
        student_explanation=student_explanation or "(none)",
        concept=concept or "(not supplied)",
        class_stats=json_dumps_or_(class_stats),
        language_hints=_language_hints(student_answer, expected_answer),
    )

    if not ollama_service.enabled():
        return _fallback_misconception(
            question, expected_answer, student_answer,
            "APP_MODE is not 'real', or OLLAMA_ENABLED is off.",
        )

    data = ollama_service.chat_json(prompt, temperature=0.0, max_tokens=200)
    validated = _validate_classification(data) if data else None
    if validated is None:
        return _fallback_misconception(
            question, expected_answer, student_answer,
            "Ollama did not return valid classification JSON.",
        )

    return {
        "mode": "real",
        "engine": f"ollama:{Config.OLLAMA_MODEL}",
        **validated,
        "warning": None,
    }


def format_alternate_explanation(
    concept: str,
    misconception_summary: str,
    grade_level: int = 3,
    preferred_language: str = "hi",
) -> dict:
    prompt = ALTERNATE_EXPLANATION_PROMPT.format(
        concept=concept or "the topic",
        summary=misconception_summary or "they are confusing two ideas",
        grade=grade_level,
    )
    if not ollama_service.enabled():
        return {
            "mode": "fallback",
            "engine": "canned-explanation",
            "explanation": DEMO_EXPLANATIONS["default"],
            "warning": "Ollama is not in use (APP_MODE=demo or daemon down). This is a canned explanation, not a live LLM.",
        }
    text = _real_generate(prompt, temperature=0.4, max_tokens=220)
    if not text:
        return {
            "mode": "fallback",
            "engine": "canned-explanation",
            "explanation": DEMO_EXPLANATIONS["default"],
            "warning": "Ollama did not produce an alternate explanation. This is a canned explanation, not a live LLM.",
        }
    return {
        "mode": "real",
        "engine": f"ollama:{Config.OLLAMA_MODEL}",
        "explanation": text[:600],
        "warning": None,
    }


def explain_doubt(hindi_question: str, context_chunks: list[str] | None = None,
                  grade_level: int = 3, preferred_language: str = "en") -> dict:
    prompt = DOUBT_EXPLANATION_PROMPT.format(
        question=hindi_question,
        context="\n".join(context_chunks) if context_chunks else "(no textbook context retrieved)",
        grade=grade_level,
        language=preferred_language,
    )
    if not ollama_service.enabled():
        return {
            "mode": "fallback",
            "engine": "canned-explanation",
            "answer": DEMO_EXPLANATIONS["default"],
            "warning": "Ollama is not in use (APP_MODE=demo or daemon down). This is a canned explanation, not a live LLM.",
        }
    text = _real_generate(prompt, temperature=0.4, max_tokens=260)
    if not text:
        return {
            "mode": "fallback",
            "engine": "canned-explanation",
            "answer": DEMO_EXPLANATIONS["default"],
            "warning": "Ollama did not produce a doubt explanation. This is a canned explanation, not a live LLM.",
        }
    return {
        "mode": "real",
        "engine": f"ollama:{Config.OLLAMA_MODEL}",
        "answer": text[:900],
        "warning": None,
    }


def explain_weak_concept(concept: str, mastery_percent: int, class_context: str = "") -> dict:
    prompt = WEAK_CONCEPT_INSIGHT_PROMPT.format(
        concept=concept,
        mastery=mastery_percent,
        context=class_context or "(none supplied)",
    )
    if not ollama_service.enabled():
        return {
            "mode": "fallback",
            "engine": "canned-insight",
            "explanation": (
                f"Students struggled with '{concept}' ({mastery_percent}% mastery). "
                "Re-teach it with the visual flashcard and a simple example."
            ),
            "warning": "Ollama is not in use (APP_MODE=demo or daemon down). This is a canned insight, not a live LLM.",
        }
    text = _real_generate(prompt, temperature=0.4, max_tokens=220)
    if not text:
        return {
            "mode": "fallback",
            "engine": "canned-insight",
            "explanation": (
                f"Students struggled with '{concept}' ({mastery_percent}% mastery). "
                "Re-teach it with the visual flashcard and a simple example."
            ),
            "warning": "Ollama did not produce an insight. This is a canned insight, not a live LLM.",
        }
    return {
        "mode": "real",
        "engine": f"ollama:{Config.OLLAMA_MODEL}",
        "explanation": text[:500],
        "warning": None,
    }


def generate_explanation(
    question: str,
    context_chunks: list[str] | None = None,
    grade_level: int = 3,
    preferred_language: str = "hi",
    weak_concepts: list[str] | None = None,
    learning_level: str = "medium",
    require_grounding: bool = False,
) -> dict:
    context_chunks = context_chunks or []
    weak_concepts = weak_concepts or []

    if require_grounding and not context_chunks:
        return {
            "mode": "fallback",
            "engine": "none",
            "answer": "",
            "warning": "Curriculum grounding is unavailable, so no textbook-backed answer was generated.",
        }

    prompt = (
        f"You are a friendly classroom assistant for grade {grade_level} children. "
        f"Learning level: {learning_level}. Preferred language: {preferred_language}. "
        f"Weak concepts to gently revisit: {', '.join(weak_concepts) or 'none'}.\n"
        "Give a child-friendly explanation with one simple example. "
        "Do not just translate. Use ONLY the textbook context. "
        "If the context is missing the answer, say so.\n\n"
        f"Context:\n{chr(10).join(context_chunks) if context_chunks else '(none retrieved)'}\n\n"
        f"Question: {question}\n"
        "Answer in 2-4 short sentences a child can understand:"
    )

    if not Config.is_demo():
        answer = _real_generate(prompt)
        if answer:
            return {"mode": "real", "engine": f"ollama:{Config.OLLAMA_MODEL}", "answer": answer, "warning": None}

    return {
        "mode": "fallback",
        "engine": "canned-explanation",
        "answer": DEMO_EXPLANATIONS["default"],
        "warning": "Ollama is not in use (APP_MODE=demo or daemon down). This is a canned explanation, not a live LLM.",
    }


QUIZ_GENERATION_PROMPT = (
    "तुम एक प्राथमिक विद्यालय के शिक्षक की सहायता करते हो।\n"
    "शिक्षक का प्रश्न/विषय: {topic}\n"
    "कक्षा: {grade_level}\n"
    "कठिनाई: {difficulty}\n\n"
    "इस विषय पर एक क्विज़ बनाओ। {n_mcq} MCQ (4 विकल्पों के साथ) और {n_short} "
    "छोटा उत्तर प्रश्न बनाओ।\n"
    "पाठ्य संदर्भ (यदि उपलब्ध हो):\n{context}\n\n"
    "केवल निम्नलिखित JSON प्रारूप में उत्तर दो (कोई अतिरिक्त पाठ नहीं):\n"
    '{{"questions": [{{"id": "q1", "type": "mcq", "prompt": "प्रश्न", '
    '"options": ["A", "B", "C", "D"], "correct_answer": "A", '
    '"concept": "अवधारणा", "difficulty": "easy"}}]}}'
)


def _validate_quiz_json(data: dict) -> list[dict] | None:
    """Validate and normalise quiz JSON returned by Ollama."""
    if not isinstance(data, dict):
        return None
    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        return None
    validated = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        qtype = q.get("type") or "mcq"
        prompt_text = (q.get("prompt") or q.get("question") or "").strip()
        if not prompt_text:
            continue
        options = q.get("options") or []
        correct = (q.get("correct_answer") or q.get("correct_option") or "").strip()
        concept = (q.get("concept") or "").strip() or "general"
        diff = (q.get("difficulty") or "medium").strip()
        qid = q.get("id") or f"q{i + 1}"
        validated.append({
            "id": str(qid),
            "type": qtype,
            "prompt": prompt_text,
            "options": options if qtype == "mcq" else [],
            "correct_answer": correct,
            "concept": concept,
            "difficulty": diff,
        })
    return validated if validated else None


def generate_quiz(topic: str, grade_level: int = 3, difficulty: str = "medium",
                  context_chunks: list[str] | None = None, n_mcq: int = 3, n_short: int = 1) -> dict:
    context_chunks = context_chunks or []
    prompt = QUIZ_GENERATION_PROMPT.format(
        topic=topic or "पौधों के भाग",
        grade_level=grade_level,
        difficulty=difficulty,
        n_mcq=n_mcq,
        n_short=n_short,
        context="\n".join(context_chunks) if context_chunks else "(कोई अतिरिक्त संदर्भ नहीं)",
    )

    if ollama_service.enabled():
        data = ollama_service.chat_json(prompt, temperature=0.3, max_tokens=800)
        questions = _validate_quiz_json(data) if data else None
        if questions:
            return {
                "mode": "real",
                "engine": f"ollama:{Config.OLLAMA_MODEL}",
                "questions": questions,
                "warning": None,
            }

    return {
        "mode": "fallback",
        "engine": "template-quiz",
        "questions": _demo_questions(difficulty, n_mcq, n_short),
        "warning": "Quiz generated from the lesson template (not a live LLM).",
    }


def _demo_questions(difficulty: str, n_mcq: int, n_short: int) -> list[dict]:
    mcqs = [q for q in DEMO_QUIZ if q["type"] == "mcq"]
    shorts = [q for q in DEMO_QUIZ if q["type"] == "short"]
    picked = mcqs[:n_mcq] + shorts[:n_short]
    for q in picked:
        q["difficulty"] = difficulty
    return [dict(q) for q in picked]


def _parse_quiz_or_demo(raw: str, difficulty: str, n_mcq: int, n_short: int) -> list[dict]:
    # If parsing fails, fall back to templates rather than returning garbage.
    return _demo_questions(difficulty, n_mcq, n_short)


def evaluate_with_llm(question: str, expected: str, student_answer: str) -> dict | None:
    prompt = (
        "You grade a class-3 short answer. Reply with exactly one line:\n"
        "verdict=<correct|partial|incorrect|misconception>;reason=<short>\n"
        f"Question: {question}\nExpected: {expected}\nStudent: {student_answer}\n"
    )
    if not ollama_service.enabled():
        return None
    raw = _real_generate(prompt)
    if not raw:
        return None
    return {"raw": raw, "engine": f"ollama:{Config.OLLAMA_MODEL}"}


def json_dumps_or_(value) -> str:
    return str(value) if value is not None else "(none)"