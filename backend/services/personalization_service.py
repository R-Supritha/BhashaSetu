"""
Teacher-facing recommendations only (per spec: no individual student profile
screens). This wraps assessment_service's weak-concept output into the
"Students are struggling with X — recommended: re-teach X" framing.

Scores, mastery percentages and weak-concept detection are computed
deterministically by assessment_service; Qwen (when active) may only add
natural-language explanation and an alternate teaching explanation, never
numbers.
"""

from backend.services import assessment_service, flashcard_service, llm_service


def recommendations_for(worksheet_id: str | None = None) -> list[dict]:
    weak = assessment_service.weak_concepts(worksheet_id)
    results = []
    for item in weak:
        card = flashcard_service.get_by_concept(item["concept"])
        results.append({
            "concept": item["concept"],
            "mastery_percent": item["mastery_percent"],
            "recommendation": f"Re-teach {item['concept'].title()} using the visual flashcard.",
            "flashcard_id": card["_id"] if card else None,
        })
    # Additive natural-language insight + alternate teaching explanation for
    # the weakest flagged concept (Qwen in real mode, labelled fallback otherwise).
    if results:
        top = weak[0]
        insight = llm_service.explain_weak_concept(
            top["concept"],
            top["mastery_percent"],
            class_context=f"worksheet: {worksheet_id or 'all-submissions'}",
        )
        alternate = llm_service.format_alternate_explanation(
            top["concept"],
            f"Students answered less than {top['mastery_percent']}% of "
            f"questions about '{top['concept']}' correctly.",
        )
        results[0]["explanation"] = insight["explanation"]
        results[0]["explanation_mode"] = insight["mode"]
        results[0]["explanation_engine"] = insight.get("engine") or ""
        results[0]["alternate_explanation"] = alternate["explanation"]
        results[0]["alternate_explanation_mode"] = alternate["mode"]
        results[0]["alternate_explanation_engine"] = alternate.get("engine") or ""
    return results
