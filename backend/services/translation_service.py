"""
Translation interface.

Priority order for Hindi↔Santali:

1. NLLB-200 (facebook/nllb-200-distilled-600M) — local offline neural MT.
   Loaded lazily on first real translation. Returns mode="real",
   engine="nllb-200" when the model produces output.
2. Bhashini DHRUVA/ULCA NMT (cloud) — used only when the environment provides
   BHASHINI_USER_ID + BHASHINI_API_KEY + BHASHINI_PIPELINE_ID and NLLB is
   unavailable. Returns mode="real", engine="bhashini".
3. Local phrase table + lesson glossary (offline) — always preserved and
   clearly labelled mode="fallback", so the classroom never breaks offline.
"""

import io
import os
import re
import sys
import unicodedata

from backend.config import Config
from backend.services.translation_engines import BhashiniDhruvaEngine, TranslationEngineUnavailable

# Suppress HF symlink warning on Windows (harmless).
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# NLLB-200 local engine. Lazy-loaded so demo/offline mode pays no cost.
_NLLB_MODEL = None
_NLLB_TOKENIZER = None
_NLLB_AVAILABLE = None  # None = not checked yet; True/False after first attempt.


def _get_nllb_engine():
    """Lazily load NLLB-200-distilled-600M. Returns (tokenizer, model) or None."""
    global _NLLB_MODEL, _NLLB_TOKENIZER, _NLLB_AVAILABLE
    if _NLLB_AVAILABLE is not None:
        if _NLLB_AVAILABLE:
            return _NLLB_TOKENIZER, _NLLB_MODEL
        return None
    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        model_name = "facebook/nllb-200-distilled-600M"
        _NLLB_TOKENIZER = AutoTokenizer.from_pretrained(model_name)
        _NLLB_MODEL = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        _NLLB_AVAILABLE = True
        return _NLLB_TOKENIZER, _NLLB_MODEL
    except Exception:
        _NLLB_AVAILABLE = False
        return None


# Bhashini cloud engine. Instantiated lazily so neither the phrasal fallback
# nor demo mode pays any cost when credentials are absent.
_bhashini_engine: "BhashiniDhruvaEngine | None" = None


def _get_bhashini_engine() -> "BhashiniDhruvaEngine | None":
    global _bhashini_engine
    if _bhashini_engine is None:
        _bhashini_engine = BhashiniDhruvaEngine()
    return _bhashini_engine if _bhashini_engine.available() else None

# Exact (normalized) phrases for the SIH demo walkthrough.
_PHRASES = {
    ("hi", "sat", "पौधों को बढ़ने के लिए धूप और पानी चाहिए।"):
        "ᱫᱟᱨᱮ ᱚᱠᱚᱭ ᱵᱟᱲᱟᱭ ᱞᱟᱹᱜᱤᱫ ᱥᱮᱛᱟᱜ ᱟᱨ ᱫᱟᱜ ᱵᱟᱹᱱᱩᱜᱼᱟ ᱾",
    ("hi", "sat", "पौधों को बढ़ने के लिए धूप चाहिए।"):
        "ᱫᱟᱨᱮ ᱵᱟᱲᱟᱭ ᱞᱟᱹᱜᱤᱫ ᱥᱮᱛᱟᱜ ᱵᱟᱹᱱᱩᱜᱼᱟ ᱾",
    ("en", "sat", "plants need sunlight to grow"):
        "ᱫᱟᱨᱮ ᱵᱟᱲᱟᱭ ᱞᱟᱹᱜᱤᱫ ᱥᱮᱛᱟᱜ ᱵᱟᱹᱱᱩᱜᱼᱟ ᱾",
    ("en", "hi", "plants need sunlight to grow"):
        "पौधों को बढ़ने के लिए धूप चाहिए।",
    ("en", "hi", "plants need sunlight and water to grow"):
        "पौधों को बढ़ने के लिए धूप और पानी चाहिए।",
    ("sat", "hi", "ᱫᱟᱨᱮ ᱚᱠᱚ ᱞᱟᱹᱜᱤᱫ ᱪᱟᱸᱰᱚ ᱠᱟᱱᱟ ᱥᱮᱛᱟᱜ ᱫᱚ ᱡᱟᱹᱨᱩᱲᱤᱭᱟᱹ ᱟᱠᱟᱱᱟ?"):
        "पौधों को धूप की जरूरत क्यों होती है?",
    ("en", "hi", "why do plants need sunlight"):
        "पौधों को धूप की जरूरत क्यों होती है?",
    ("en", "sat", "why do plants need sunlight"):
        "ᱫᱟᱨᱮ ᱚᱠᱚ ᱞᱟᱹᱜᱤᱫ ᱪᱟᱸᱰᱚ ᱠᱟᱱᱟ ᱥᱮᱛᱟᱜ ᱫᱚ ᱡᱟᱹᱨᱩᱲᱤᱭᱟᱹ ᱟᱠᱟᱱᱟ?",
}

# Word-level glossary for the Parts of a Plant lesson (fallback only).
_GLOSSARY = {
    ("hi", "sat"): {
        "पौधा": "ᱫᱟᱨᱮ", "पौधे": "ᱫᱟᱨᱮ", "पौधों": "ᱫᱟᱨᱮ",
        "जड़": "ᱨᱮᱦᱮᱫ", "जड़ें": "ᱨᱮᱦᱮᱫ",
        "तना": "ᱜᱚᱜᱚ", "पत्ती": "ᱥᱟᱠᱟᱢ", "पत्तियां": "ᱥᱟᱠᱟᱢ", "पत्ते": "ᱥᱟᱠᱟᱢ",
        "फूल": "ᱵᱟᱦᱟ", "फल": "ᱡᱚ", "बीज": "ᱡᱟᱝ",
        "पानी": "ᱫᱟᱜ", "धूप": "ᱥᱮᱛᱟᱜ", "सूरज": "ᱥᱤᱧ",
        "मिट्टी": "ᱦᱟᱥᱟ", "हवा": "ᱦᱚᱭ",
    },
    ("en", "sat"): {
        "plant": "ᱫᱟᱨᱮ", "plants": "ᱫᱟᱨᱮ", "root": "ᱨᱮᱦᱮᱫ", "roots": "ᱨᱮᱦᱮᱫ",
        "stem": "ᱜᱚᱜᱚ", "leaf": "ᱥᱟᱠᱟᱢ", "leaves": "ᱥᱟᱠᱟᱢ",
        "flower": "ᱵᱟᱦᱟ", "fruit": "ᱡᱚ", "seed": "ᱡᱟᱝ",
        "water": "ᱫᱟᱜ", "sunlight": "ᱥᱮᱛᱟᱜ", "sun": "ᱥᱤᱧ", "soil": "ᱦᱟᱥᱟ",
        "grow": "ᱵᱟᱲᱟᱭ", "need": "ᱵᱟᱹᱱᱩᱜ", "needs": "ᱵᱟᱹᱱᱩᱜ",
    },
    ("en", "hi"): {
        "plant": "पौधा", "plants": "पौधे", "root": "जड़", "stem": "तना",
        "leaf": "पत्ती", "flower": "फूल", "fruit": "फल", "seed": "बीज",
        "water": "पानी", "sunlight": "धूप", "grow": "बढ़ना", "need": "जरूरत",
    },
    ("sat", "hi"): {
        "ᱫᱟᱨᱮ": "पौधा", "ᱨᱮᱦᱮᱫ": "जड़", "ᱜᱚᱜᱚ": "तना", "ᱥᱟᱠᱟᱢ": "पत्ती",
        "ᱵᱟᱦᱟ": "फूल", "ᱡᱚ": "फल", "ᱡᱟᱝ": "बीज", "ᱫᱟᱜ": "पानी",
        "ᱥᱮᱛᱟᱜ": "धूप", "ᱥᱤᱧ": "सूरज",
    },
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", (text or "").strip())
    text = re.sub(r"\s+", " ", text)
    return text


def _norm_key(text: str) -> str:
    text = _normalize(text).lower()
    text = re.sub(r"[.?!।,;:\"']+", "", text).strip()
    return text


def _phrase_lookup(source: str, target: str, text: str) -> str | None:
    exact = _PHRASES.get((source, target, _normalize(text)))
    if exact:
        return exact
    needle = _norm_key(text)
    for (s, t, src), dst in _PHRASES.items():
        if s == source and t == target and _norm_key(src) == needle:
            return dst
    return None


def _glossary_translate(text: str, source: str, target: str) -> tuple[str, bool]:
    table = _GLOSSARY.get((source, target), {})
    if not table:
        return text, False
    # Longest-key first so "sunlight" wins over "sun".
    keys = sorted(table.keys(), key=len, reverse=True)
    out = text
    hit = False
    if source == "en":
        tokens = re.findall(r"[A-Za-z]+|[^A-Za-z]+", text)
        built = []
        for tok in tokens:
            mapped = table.get(tok.lower())
            if mapped:
                built.append(mapped)
                hit = True
            else:
                built.append(tok)
        return "".join(built), hit
    for key in keys:
        if key in out:
            out = out.replace(key, table[key])
            hit = True
    return out, hit


def _real_indictrans2(text: str, source: str, target: str) -> str:
    """Local IndicTrans2 inference. Santali is possible in theory (sat_Olck)
    but no usable local checkpoint is obtainable (Hugging Face gating)."""
    if "sat" in (source, target):
        raise RuntimeError(
            "No local IndicTrans2 checkpoint with sat_Olck coverage is available "
            "(official checkpoints are license-gated on Hugging Face)."
        )
    if Config.INDICTRANS2_PATH:
        raise NotImplementedError("IndicTrans2 weights are configured but not loaded.")
    raise NotImplementedError("IndicTrans2 is not configured.")


# NLLB-200 language code mapping: our internal codes → NLLB BOS token strings.
# NLLB uses sat_Beng for Santali (outputs Ol Chiki script despite the name).
_NLLB_LANG_MAP = {
    "hi": "hin_Deva",
    "sat": "sat_Beng",
    "en": "eng_Latn",
}


def _real_nllb_translate(text: str, source: str, target: str) -> str:
    """Run NLLB-200-distilled-600M locally. Raises RuntimeError on failure."""
    engine = _get_nllb_engine()
    if engine is None:
        raise RuntimeError("NLLB-200 model could not be loaded.")
    tokenizer, model = engine

    src_code = _NLLB_LANG_MAP.get(source)
    tgt_code = _NLLB_LANG_MAP.get(target)
    if not src_code or not tgt_code:
        raise RuntimeError(
            f"NLLB-200 does not support the pair {source}→{target}."
        )

    tokenizer.src_lang = src_code
    encoded = tokenizer(text, return_tensors="pt")
    generated = model.generate(
        **encoded,
        forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_code),
        max_new_tokens=128,
    )
    translated = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
    return translated.strip()


def _real_bhashini_translate(text: str, source: str, target: str) -> str:
    """Run Bhashini DHRUVA NMT. Raises TranslationEngineUnavailable on any failure."""
    engine = _get_bhashini_engine()
    if engine is None:
        raise TranslationEngineUnavailable(
            "Bhashini credentials are not configured. Set BHASHINI_USER_ID, "
            "BHASHINI_API_KEY and BHASHINI_PIPELINE_ID to enable real translation."
        )
    return engine.translate(text, source, target)


def translate(text: str, source_language: str, target_language: str) -> dict:
    source_language = (source_language or "hi").lower()
    target_language = (target_language or "sat").lower()
    text = _normalize(text)

    if source_language == target_language:
        return {
            "mode": "passthrough",
            "engine": "none",
            "translated_text": text,
            "warning": None,
        }

    involves_sat = "sat" in (source_language, target_language)

    # Priority 1: NLLB-200 local neural MT (works offline, no credentials needed).
    # Only used for Santali-involved pairs where NLLB has coverage (hi↔sat, en↔sat).
    if involves_sat and not Config.is_demo():
        try:
            translated = _real_nllb_translate(text, source_language, target_language)
            return {
                "mode": "real",
                "engine": "nllb-200",
                "translated_text": translated,
                "warning": None,
            }
        except Exception:
            pass

    # Priority 2: Bhashini cloud NMT (requires credentials).
    if involves_sat and not Config.is_demo():
        try:
            translated = _real_bhashini_translate(text, source_language, target_language)
            return {
                "mode": "real",
                "engine": "bhashini",
                "translated_text": translated,
                "warning": None,
            }
        except Exception:
            pass

    if not involves_sat and not Config.is_demo() and Config.INDICTRANS2_PATH:
        try:
            translated = _real_indictrans2(text, source_language, target_language)
            return {
                "mode": "real",
                "engine": "IndicTrans2",
                "translated_text": translated,
                "warning": None,
            }
        except Exception as exc:
            return {
                "mode": "fallback",
                "engine": "none",
                "translated_text": text,
                "warning": f"IndicTrans2 unavailable ({exc.__class__.__name__}).",
            }

    phrase = _phrase_lookup(source_language, target_language, text)
    if phrase:
        return {
            "mode": "fallback",
            "engine": "demo-phrase-table",
            "translated_text": phrase,
            "warning": (
                "NLLB-200 neural MT was attempted but did not produce a result for "
                "this input. Using the classroom phrase table (labelled fallback)."
                if involves_sat else None
            ),
        }

    glossed, hit = _glossary_translate(text, source_language, target_language)
    if hit:
        return {
            "mode": "fallback",
            "engine": "lesson-glossary",
            "translated_text": glossed,
            "warning": (
                "No full-sentence translation for this input. "
                "Used the Parts-of-a-Plant glossary (not a neural MT model)."
            ),
        }

    return {
        "mode": "fallback",
        "engine": "none",
        "translated_text": text,
        "warning": (
            "NLLB-200 neural MT was attempted but could not translate this input. "
            "Original text shown."
            if involves_sat
            else "No translation available for this language pair."
        ),
    }
