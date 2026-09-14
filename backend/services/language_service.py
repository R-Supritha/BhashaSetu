"""
Language identification interface.

Real mode may wrap IndicLID for Hindi/other Indic languages it actually
supports. Santali (Ol Chiki) is detected with a script heuristic because
IndicLID does not reliably cover Santali — we never report it as IndicLID.
"""

from backend.config import Config

_OL_CHIKI = (0x1C50, 0x1C7F)
_DEVANAGARI = (0x0900, 0x097F)

SUPPORTED = ("hi", "sat", "en")


def _script_counts(text: str) -> dict:
    ol = dev = latin = 0
    for ch in text:
        code = ord(ch)
        if _OL_CHIKI[0] <= code <= _OL_CHIKI[1]:
            ol += 1
        elif _DEVANAGARI[0] <= code <= _DEVANAGARI[1]:
            dev += 1
        elif ch.isascii() and ch.isalpha():
            latin += 1
    return {"sat": ol, "hi": dev, "en": latin}


def _heuristic(text: str) -> tuple[str, float]:
    stripped = (text or "").strip()
    if not stripped:
        return "unknown", 0.0
    counts = _script_counts(stripped)
    total = sum(counts.values()) or 1
    language = max(counts, key=counts.get)
    if counts[language] == 0:
        return "unknown", 0.0
    confidence = round(counts[language] / total, 2)
    return language, confidence


def _real_identify(text: str) -> dict:
    """IndicLID hook — only for languages that model actually supports."""
    if Config.INDICLID_PATH:
        raise NotImplementedError("IndicLID weights are configured but not loaded.")
    raise NotImplementedError("IndicLID is not configured.")


def identify(text: str) -> dict:
    """
    Returns:
      language, confidence, mode (real|heuristic|fallback),
      engine, supported (bool), warning
    """
    language, confidence = _heuristic(text)

    if not Config.is_demo() and language in ("hi", "en") and Config.INDICLID_PATH:
        try:
            result = _real_identify(text)
            result.setdefault("mode", "real")
            result.setdefault("engine", "IndicLID")
            result["supported"] = result.get("language") in SUPPORTED
            return result
        except Exception:
            pass

    engine = "ol-chiki-script" if language == "sat" else "script-heuristic"
    warning = None
    if language == "sat":
        warning = "Santali detected via Ol Chiki script, not IndicLID."
    elif language == "unknown":
        warning = "Could not identify language."

    return {
        "language": language,
        "confidence": confidence,
        "mode": "heuristic",
        "engine": engine,
        "supported": language in SUPPORTED,
        "warning": warning,
    }
