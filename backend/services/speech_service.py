"""
Speech-to-text interface.

Browser / typed transcripts are first-class: if `text` is provided, it is
used as the transcript (ASR skipped). Real Hindi ASR runs via the local Vosk
model whenever the model folder exists AND the app is not in demo mode
(real / typing path is otherwise unchanged).

Santali (Ol Chiki) ASR is never claimed unless BHASHINI_ASR_URL is set.
"""

import json
import os
import subprocess
import threading
import wave

from backend.config import Config
from backend.services import language_service

DEMO_TRANSCRIPTS = {
    "teacher_default": {
        "language": "hi",
        "text": "पौधों को बढ़ने के लिए धूप और पानी चाहिए।",
        "gloss": "Plants need sunlight and water to grow.",
    },
    "teacher_sunlight": {
        "language": "hi",
        "text": "पौधों को बढ़ने के लिए धूप चाहिए।",
        "gloss": "Plants need sunlight to grow.",
    },
    "student_doubt": {
        "language": "sat",
        "text": "ᱫᱟᱨᱮ ᱚᱠᱚ ᱞᱟᱹᱜᱤᱫ ᱪᱟᱸᱰᱚ ᱠᱟᱱᱟ ᱥᱮᱛᱟᱜ ᱫᱚ ᱡᱟᱹᱨᱩᱲᱤᱭᱟᱹ ᱟᱠᱟᱱᱟ?",
        "gloss": "Why do plants need sunlight?",
    },
}

_VOSK_MODEL = None
_VOSK_LOCK = threading.Lock()
_FFMPEG_EXE = None


def _ffmpeg_path() -> str | None:
    """Path to the ffmpeg binary bundled with imageio-ffmpeg, if importable."""
    global _FFMPEG_EXE
    if _FFMPEG_EXE is None:
        try:
            import imageio_ffmpeg
            _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            _FFMPEG_EXE = None
    return _FFMPEG_EXE


def _vosk_model():
    """Load (once) and return the Vosk Hindi model, or None if unavailable."""
    global _VOSK_MODEL
    if _VOSK_MODEL is not None:
        return _VOSK_MODEL
    if not Config.VOSK_ASR_MODEL_DIR or not os.path.isdir(Config.VOSK_ASR_MODEL_DIR):
        return None
    with _VOSK_LOCK:
        if _VOSK_MODEL is None:
            try:
                from vosk import Model
                _VOSK_MODEL = Model(Config.VOSK_ASR_MODEL_DIR)
            except Exception:
                _VOSK_MODEL = False
    return _VOSK_MODEL if _VOSK_MODEL is not False else None


def _audio_to_wav16k(audio_bytes: bytes) -> tuple[bytes, int]:
    """Decode arbitrary browser audio (webm/opus/wav/mp3) to 16 kHz mono PCM."""
    import tempfile

    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("ffmpeg (imageio_ffmpeg) not available for audio decode.")
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as src:
        src.write(audio_bytes)
        src_path = src.name
    out_path = None
    try:
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        cmd = [
            ffmpeg, "-y", "-nostdin", "-i", src_path,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-f", "wav", out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError("ffmpeg failed to decode audio.")
        with wave.open(out_path, "rb") as w:
            rate = w.getframerate()
            frames = w.readframes(w.getnframes())
        return frames, rate
    finally:
        for p in (src_path, out_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _transcribe_with_vosk(audio_bytes: bytes) -> str:
    """Run the local Vosk Hindi model on the raw audio; raise if unusable."""
    from vosk import KaldiRecognizer

    model = _vosk_model()
    if model is None:
        raise RuntimeError("Vosk model folder not found.")
    frames, rate = _audio_to_wav16k(audio_bytes)
    if not frames:
        raise RuntimeError("Decoded audio is empty.")
    recognizer = KaldiRecognizer(model, rate)
    recognizer.AcceptWaveform(frames)
    text = json.loads(recognizer.FinalResult()).get("text", "").strip()
    if not text:
        raise RuntimeError("Vosk returned no speech.")
    return text


def _real_transcribe(audio_bytes: bytes, expected_language: str) -> dict:
    # 1) Local Hindi ASR (Vosk, offline) — real pipeline when not in demo mode.
    if expected_language != "sat":
        try:
            text = _transcribe_with_vosk(audio_bytes)
            return {
                "language": "hi",
                "text": text,
                "engine": "vosk-hi",
                "warning": "Transcribed with the local Vosk Hindi model.",
            }
        except RuntimeError as exc:
            raise RuntimeError(f"Vosk Hindi ASR unavailable: {exc}")
    if expected_language == "sat" and not Config.BHASHINI_ASR_URL:
        raise RuntimeError("No Santali ASR backend configured.")
    if Config.BHASHINI_ASR_URL:
        raise NotImplementedError("Bhashini ASR URL is set but the client is not wired.")
    if Config.INDICCONFORMER_PATH and expected_language != "sat":
        raise NotImplementedError("IndicConformer path is set but the model is not loaded.")
    raise NotImplementedError("No ASR backend configured.")


def transcribe(
    audio_bytes: bytes | None = None,
    expected_language: str = "hi",
    demo_key: str = "teacher_default",
    text: str | None = None,
) -> dict:
    """
    Returns mode, language, text, engine, warning.
    """
    if text and text.strip():
        lid = language_service.identify(text)
        return {
            "mode": "text-input",
            "engine": "typed-or-browser-stt",
            "language": lid["language"] if lid["language"] != "unknown" else expected_language,
            "text": text.strip(),
            "warning": "Using provided text (microphone ASR not required).",
        }

    if audio_bytes and not Config.is_demo():
        try:
            result = _real_transcribe(audio_bytes, expected_language)
            result["mode"] = "real"
            result.setdefault("engine", "asr")
            result.setdefault("warning", None)
            return result
        except Exception as exc:
            sample = DEMO_TRANSCRIPTS.get(demo_key, DEMO_TRANSCRIPTS["teacher_default"])
            return {
                "mode": "fallback",
                "engine": "demo-transcript",
                "language": sample["language"],
                "text": sample["text"],
                "warning": (
                    f"Speech recognition unavailable ({exc.__class__.__name__}). "
                    "Showing a demo transcript. You can also type the sentence."
                ),
            }

    sample = DEMO_TRANSCRIPTS.get(demo_key, DEMO_TRANSCRIPTS["teacher_default"])
    warning = None
    if audio_bytes:
        warning = (
            "Audio was received but no ASR engine is configured. "
            "Using the demo transcript. Type text as a fallback."
        )
    elif expected_language == "sat":
        warning = (
            "Santali ASR is not configured (no local Santali ASR engine is loaded). "
            "Using the demo Santali question; typed Ol Chiki is also accepted."
        )

    return {
        "mode": "demo",
        "engine": "demo-transcript",
        "language": sample["language"],
        "text": sample["text"],
        "warning": warning,
    }
