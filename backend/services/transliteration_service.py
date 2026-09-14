"""
Transliteration (script change) — NOT translation (language change).

Hindi: IndicXlit when configured; otherwise a labelled fallback.
Santali: Ol Chiki ↔ Latin using the published Ol Chiki letter values.
IndicXlit does not cover Santali; we never claim that it does.
"""

from backend.config import Config

# Ol Chiki letters → ISO-style Latin (approx. Santali romanization).
_OL_CHIKI_TO_LATIN = {
    "ᱚ": "o", "ᱟ": "a", "ᱤ": "i", "ᱩ": "u", "ᱮ": "e", "ᱳ": "o",
    "ᱠ": "k", "ᱜ": "g", "ᱝ": "ng", "ᱪ": "c", "ᱡ": "j", "ᱧ": "nj",
    "ᱴ": "t", "ᱰ": "d", "ᱬ": "n", "ᱛ": "t", "ᱫ": "d", "ᱱ": "n",
    "ᱯ": "p", "ᱵ": "b", "ᱢ": "m", "ᱭ": "y", "ᱨ": "r", "ᱞ": "l",
    "ᱣ": "w", "ᱥ": "s", "ᱦ": "h", "ᱲ": "r", "ᱶ": "w", "ᱷ": "h",
    "ᱸ": "n", "ᱹ": "", "ᱺ": "", "ᱻ": "", "ᱼ": "-", "ᱽ": "'",
    "᱾": ".", "᱿": ".",
}

_LATIN_TO_OL_CHIKI_DIGRAPHS = [
    ("ng", "ᱝ"), ("nj", "ᱧ"),
]
_LATIN_TO_OL_CHIKI = {
    "o": "ᱚ", "a": "ᱟ", "i": "ᱤ", "u": "ᱩ", "e": "ᱮ",
    "k": "ᱠ", "g": "ᱜ", "c": "ᱪ", "j": "ᱡ",
    "t": "ᱛ", "d": "ᱫ", "n": "ᱱ", "p": "ᱯ", "b": "ᱵ",
    "m": "ᱢ", "y": "ᱭ", "r": "ᱨ", "l": "ᱞ", "w": "ᱣ",
    "s": "ᱥ", "h": "ᱦ",
}


def _ol_chiki_to_latin(text: str) -> str:
    return "".join(_OL_CHIKI_TO_LATIN.get(ch, ch) for ch in text)


def _latin_to_ol_chiki(text: str) -> str:
    lower = text.lower()
    for src, dst in _LATIN_TO_OL_CHIKI_DIGRAPHS:
        lower = lower.replace(src, dst)
    return "".join(_LATIN_TO_OL_CHIKI.get(ch, ch) for ch in lower)


def _real_indicxlit(text: str, source_script: str, target_script: str) -> str:
    if Config.INDICXLIT_PATH:
        raise NotImplementedError("IndicXlit weights are configured but not loaded.")
    raise NotImplementedError("IndicXlit is not configured.")


def transliterate(text: str, source_language: str, direction: str = "native_to_roman") -> dict:
    """
    direction: native_to_roman | roman_to_native
    """
    text = text or ""
    source_language = (source_language or "").lower()

    if source_language == "sat":
        if direction == "roman_to_native":
            out = _latin_to_ol_chiki(text)
        else:
            out = _ol_chiki_to_latin(text)
        return {
            "mode": "rule-based",
            "engine": "ol-chiki-map",
            "transliterated_text": out,
            "warning": "Santali transliteration is a rule-based Ol Chiki map, not IndicXlit.",
        }

    if source_language == "hi" and not Config.is_demo() and Config.INDICXLIT_PATH:
        try:
            out = _real_indicxlit(text, "devanagari", "latin")
            return {"mode": "real", "engine": "IndicXlit", "transliterated_text": out, "warning": None}
        except Exception as exc:
            return {
                "mode": "fallback",
                "engine": "none",
                "transliterated_text": text,
                "warning": f"IndicXlit unavailable ({exc.__class__.__name__}). Showing original script.",
            }

    return {
        "mode": "fallback",
        "engine": "none",
        "transliterated_text": text,
        "warning": "Hindi transliteration (IndicXlit) is not configured; original script kept.",
    }
