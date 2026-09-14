"""
Central configuration for BhashaSetu.

Everything that differs between a laptop demo and a "real AI" run lives here,
loaded from environment variables (see .env.example). Nothing below should be
hard-coded elsewhere in the app — services should import `Config` and read
from it, so switching APP_MODE or model names never means touching business
logic.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root regardless of current working directory.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # --- App mode -----------------------------------------------------
    # "demo": every AI service returns canned/simulated data. No local models,
    #         no Ollama, no internet required. This is what runs out of the box.
    # "real": services attempt to call actual ASR/translation/LLM backends and
    #         fall back to a clearly-labelled demo response if unavailable.
    APP_MODE = os.getenv("APP_MODE", "demo").strip().lower()

    # --- Flask ----------------------------------------------------------
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), default=True)
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    # --- Ollama ----------------------------------------------------------
    # OLLAMA_ENABLED=true (default) lets AI text features attempt the local
    # daemon when APP_MODE=real. If the daemon is down the app falls back and
    # labels the answer — it never crashes or silently pretends.
    OLLAMA_ENABLED = _bool(os.getenv("OLLAMA_ENABLED"), default=True)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "45"))

    # --- Optional language backends (never claimed for unsupported langs) --
    # Vosk Hindi ASR model (./models/vosk-model-small-hi-0.22 by default).
    # When the folder exists, real (offline) Hindi ASR runs whenever the app is
    # not in demo mode; otherwise /api/speech/transcribe keeps demo transcripts.
    VOSK_ASR_MODEL_DIR = os.getenv("VOSK_ASR_MODEL_DIR", "./models/vosk-model-small-hi-0.22")

    INDICTRANS2_PATH = os.getenv("INDICTRANS2_PATH", "")
    INDICLID_PATH = os.getenv("INDICLID_PATH", "")
    INDICXLIT_PATH = os.getenv("INDICXLIT_PATH", "")
    INDICCONFORMER_PATH = os.getenv("INDICCONFORMER_PATH", "")

    # Translation endpoints are optional. Keep declarations in environment variables
    # so actual deployment credentials and URLs never appear in source code.
    # Bhashini uses the DHRUVA/ULCA pipeline flow: BHASHINI_USER_ID +
    # BHASHINI_API_KEY + BHASHINI_PIPELINE_ID. When all three are present and the
    # app is not in demo mode, /api/translate attempts REAL Bhashini NMT first and
    # falls back to the phrase/glossary table on any failure or offline state.
    BHASHINI_USER_ID = os.getenv("BHASHINI_USER_ID", "")
    BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY", "")
    BHASHINI_PIPELINE_ID = os.getenv("BHASHINI_PIPELINE_ID", "")
    BHASHINI_TRANSLATION_TIMEOUT = int(os.getenv("BHASHINI_TRANSLATION_TIMEOUT", "30"))

    BHASHINI_ASR_URL = os.getenv("BHASHINI_ASR_URL", "")
    BHASHINI_TTS_URL = os.getenv("BHASHINI_TTS_URL", "")

    # IndicTrans2 supports Santali (sat_Olck) but is not usable locally in this
    # environment: the AI4Bharat objectstore fairseq checkpoints return HTTP 403,
    # the official Hugging Face copies are gated, and fairseq/IndicTransToolkit
    # have no Windows wheels (Cython builds require MSVC). Genuine Hindi↔Santali
    # MT is therefore only "real" via a configured Bhashini pipeline.
    SANTALI_MT_SUPPORTED = bool(BHASHINI_USER_ID and BHASHINI_API_KEY and BHASHINI_PIPELINE_ID)
    SANTALI_ASR_SUPPORTED = bool(BHASHINI_ASR_URL)
    SANTALI_TTS_SUPPORTED = bool(BHASHINI_TTS_URL)

    # --- RAG -------------------------------------------------------------
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
    RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.12"))

    # --- Storage ----------------------------------------------------------
    # No MongoDB for the prototype: everything lives in JSON files under
    # DATA_DIR, accessed through backend/database/json_store.py. That module
    # exposes a Mongo-collection-shaped interface (find/find_one/insert_one/
    # update_one) so swapping in real MongoDB later is a storage-layer change,
    # not a rewrite of routes/services.
    DATA_DIR = (BASE_DIR / os.getenv("DATA_DIR", "./data")).resolve()

    @classmethod
    def is_demo(cls) -> bool:
        return cls.APP_MODE != "real"
