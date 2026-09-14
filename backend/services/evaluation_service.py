"""
Answer evaluation that is not exact-string-only.

MCQs still use the keyed option. Short answers use token overlap, a small
synonym map, and optional Ollama when APP_MODE=real.
"""

import re
from backend.config import Config
from backend.services import llm_service

_SYNONYMS = {
    "sunlight": {"sun", "sunshine", "light", "धूप", "सूरज", "ᱥᱮᱛᱟᱜ"},
    "root": {"roots", "जड़", "जड़ें", "ᱨᱮᱦᱮᱫ"},
    "leaf": {"leaves", "पत्ती", "पत्ते", "ᱥᱟᱠᱟᱢ"},
    "flower": {"flowers", "फूल", "ᱵᱟᱦᱟ", "seeds"},
    "water": {"पानी", "moisture", "ᱫᱟᱜ"},
    "food": {"photosynthesis", "sugar", "खाना"},
    "soil": {"मिट्टी", "ground", "earth", "ᱦᱟᱥᱟ"},
}

_MISCONCEPTIONS = [
    (re.compile(r"eat soil|food from soil|मिट्टी खा", re.I),
     "Plants do not eat soil; roots take water and minerals, leaves make food."),
    (re.compile(r"do not need (sun|light)|without sunlight|धूप नहीं", re.I),
     "Plants need sunlight to make food in their leaves."),
]


def _norm(text: str) -> str:
    return re.sub(r"[^\w\u0900-\u097F\u1C50-\u1C7F]+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return set(_norm(text).split())


def _expand(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for token in list(tokens):
        for canonical, alts in _SYNONYMS.items():
            if token == canonical or token in alts:
                out.add(canonical)
                out |= {a.lower() for a in alts}
    return out


def evaluate_answer(question: dict, student_answer: str) -> dict:
    qtype = question.get("type") or ("mcq" if question.get("options") else "short")
    expected = question.get("correct_answer") or question.get("correct_option") or ""
    concept = question.get("concept") or ""
    given = (student_answer or "").strip()

    if qtype == "mcq":
        ok = _norm(given) == _norm(str(expected))
        return {
            "verdict": "correct" if ok else "incorrect",
            "score": 1.0 if ok else 0.0,
            "method": "option-match",
            "expected": expected,
            "student_answer": given,
            "concept": concept,
            "reason": "Selected the keyed option." if ok else "Different option from the answer key.",
            "misconception": None,
        }

    if not given:
        return {
            "verdict": "incorrect",
            "score": 0.0,
            "method": "empty",
            "expected": expected,
            "student_answer": given,
            "concept": concept,
            "reason": "No answer given.",
            "misconception": None,
        }

    if _norm(given) == _norm(str(expected)):
        return {
            "verdict": "correct",
            "score": 1.0,
            "method": "normalized-match",
            "expected": expected,
            "student_answer": given,
            "concept": concept,
            "reason": "Answer matches the expected meaning (normalized).",
            "misconception": None,
        }

    for pattern, note in _MISCONCEPTIONS:
        if pattern.search(given):
            return {
                "verdict": "misconception",
                "score": 0.0,
                "method": "misconception-pattern",
                "expected": expected,
                "student_answer": given,
                "concept": concept,
                "reason": note,
                "misconception": note,
            }

    st = _expand(_tokens(given))
    ex = _expand(_tokens(str(expected)))
    if concept:
        ex = _expand(ex | {concept})
    if not ex:
        jaccard = 0.0
    else:
        jaccard = len(st & ex) / len(st | ex)

    if not Config.is_demo():
        llm = llm_service.evaluate_with_llm(question.get("prompt", ""), str(expected), given)
        if llm and "verdict=" in llm["raw"].lower():
            raw = llm["raw"].lower()
            verdict = "partial"
            if "verdict=correct" in raw:
                verdict = "correct"
            elif "verdict=misconception" in raw:
                verdict = "misconception"
            elif "verdict=incorrect" in raw:
                verdict = "incorrect"
            score = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0, "misconception": 0.0}[verdict]
            return {
                "verdict": verdict,
                "score": score,
                "method": llm["engine"],
                "expected": expected,
                "student_answer": given,
                "concept": concept,
                "reason": llm["raw"][:240],
                "misconception": "Possible misconception — see reason." if verdict == "misconception" else None,
            }

    if jaccard >= 0.45 or (len(st & ex) >= 2 and "sunlight" in (st | ex) and "food" in (st | ex)):
        verdict, score, reason = "correct", 1.0, "Student answer shows the same key ideas."
    elif jaccard >= 0.2 or (st & ex):
        verdict, score, reason = "partial", 0.5, "Some key ideas are present; the answer is incomplete."
    else:
        verdict, score, reason = "incorrect", 0.0, "Answer does not show the expected understanding."

    return {
        "verdict": verdict,
        "score": score,
        "method": "semantic-overlap",
        "expected": expected,
        "student_answer": given,
        "concept": concept,
        "reason": reason,
        "misconception": None,
        "overlap": round(jaccard, 3),
    }
