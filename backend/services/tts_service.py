"""
Text-to-speech interface.

Santali TTS is only "real" when BHASHINI_TTS_URL is configured AND the
deployed pipeline actually lists sat. Default: labelled fallback, text shown.
Hindi may use the browser SpeechSynthesis API (frontend) when no server TTS
is configured — the backend reports `browser_tts: true` for hi/en.
"""

from backend.config import Config


def synthesize(text: str, language: str = "sat") -> dict:
    language = (language or "sat").lower()
    text = (text or "").strip()

    if language == "sat":
        if Config.BHASHINI_TTS_URL and not Config.is_demo():
            try:
                raise NotImplementedError("Bhashini TTS URL is set but the client is not wired.")
            except Exception as exc:
                return {
                    "mode": "fallback",
                    "engine": "none",
                    "audio_url": None,
                    "browser_tts": False,
                    "warning": (
                        f"Santali TTS unavailable ({exc.__class__.__name__}). "
                        "Showing Ol Chiki text only."
                    ),
                }
        return {
            "mode": "fallback",
            "engine": "none",
            "audio_url": None,
            "browser_tts": False,
            "warning": (
                "No Santali TTS engine is configured. "
                "Ol Chiki text is shown; audio is skipped (not silently faked)."
            ),
        }

    # Hindi / English: ask the classroom UI to use the browser voice if any.
    return {
        "mode": "fallback",
        "engine": "browser-speech-synthesis",
        "audio_url": None,
        "browser_tts": True,
        "warning": "Server TTS is not configured. The tablet may speak Hindi/English via the browser.",
    }
