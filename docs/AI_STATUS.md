# AI Component Status

This document shows which AI components are **REAL** (genuine model inference), **FALLBACK** (deterministic heuristic with honest labelling), or **MOCK** (stub returning placeholder data) in the current build.

---

## Summary Table

| Component | Demo Mode | Real Mode (no services) | Real Mode (with services) |
|-----------|-----------|------------------------|--------------------------|
| **Translation (Hindi↔Santali)** | FALLBACK | FALLBACK | REAL (NLLB-200 / Bhashini) |
| **Speech Recognition (ASR)** | MOCK | FALLBACK | REAL (Vosk offline) |
| **Language Identification** | MOCK | MOCK | MOCK (script heuristic) |
| **LLM (Ollama)** | N/A | FALLBACK | REAL (qwen2.5:3b-instruct) |
| **Worksheet Scoring** | REAL | REAL | REAL |
| **Misconception Detection** | FALLBACK | FALLBACK | REAL (Ollama LLM) |
| **RAG Retrieval** | FALLBACK | FALLBACK | REAL (ChromaDB + TF-IDF) |
| **OCR (Textbook Upload)** | REAL | REAL | REAL (pypdf + pytesseract) |
| **Dictionary Lookup** | REAL | REAL | REAL (deterministic) |
| **Flashcard Retrieval** | REAL | REAL | REAL (deterministic) |
| **Assessment Analytics** | REAL | REAL | REAL (deterministic) |
| **TTS** | MOCK | MOCK | MOCK (browser-side only) |

---

## Detailed Component Status

### Translation — `backend/services/translation_service.py`

**Priority chain:** NLLB-200 (local) → Bhashini DHRUVA (cloud) → phrase table → glossary → passthrough

| Engine | Status | When Used |
|--------|--------|-----------|
| NLLB-200 (facebook/nllb-200-distilled-600M) | REAL | `APP_MODE=real`, model loaded successfully |
| Bhashini DHRUVA NMT | REAL | `APP_MODE=real`, credentials configured |
| Phrase table (7 exact phrases) | FALLBACK | Always available, clearly labelled |
| Lesson glossary (word-level) | FALLBACK | Always available, clearly labelled |

**How to enable real translation:**
1. Set `APP_MODE=real` in `.env`
2. NLLB-200 auto-downloads on first use (~1.2GB, requires `transformers` package)
3. OR configure `BHASHINI_USER_ID`, `BHASHINI_API_KEY`, `BHASHINI_PIPELINE_ID` for cloud NMT

### Speech Recognition — `backend/services/speech_service.py`

| Engine | Status | When Used |
|--------|--------|-----------|
| Vosk Hindi Small | REAL | `APP_MODE=real` + model folder exists |
| Browser Web Speech API | REAL | Client-side, sends transcript to server |
| Demo transcript | MOCK | `APP_MODE=demo` or no Vosk model |

**How to enable real ASR:**
1. Download `vosk-model-small-hi-0.22` from https://alphacephei.com/vosk/models
2. Extract into `models/vosk-model-small-hi-0.22/`
3. Set `APP_MODE=real` in `.env`

### Language Identification — `backend/services/language_service.py`

| Method | Status | Notes |
|--------|--------|-------|
| Script heuristic | MOCK | Ol Chiki → Santali, Devanagari → Hindi, Latin → English |
| IndicLID | Not wired | Hook exists but not connected |

### LLM (Ollama) — `backend/services/llm_service.py` + `ollama_service.py`

| Function | Demo Mode | Real Mode |
|----------|-----------|-----------|
| Misconception classification | FALLBACK (heuristic) | REAL (Ollama LLM) |
| Doubt explanation | FALLBACK (canned) | REAL (Ollama LLM) |
| Worksheet generation | FALLBACK (canned) | REAL (Ollama LLM) |
| Weak concept insight | FALLBACK (canned) | REAL (Ollama LLM) |
| Alternate explanation | FALLBACK (canned) | REAL (Ollama LLM) |

**How to enable real LLM:**
1. Install Ollama: https://ollama.ai
2. Pull model: `ollama pull qwen2.5:3b-instruct`
3. Set `OLLAMA_ENABLED=true` and `APP_MODE=real` in `.env`

### Worksheet Scoring — `backend/services/worksheet_service.py`

**Always REAL.** Scoring is deterministic — MCQ answer matching cannot be altered by LLM. The LLM is only used for optional misconception analysis on open-ended explanations, which is additive and does not affect scores.

### RAG (Retrieval-Augmented Generation) — `backend/services/rag_service.py`

| Component | Status | Notes |
|-----------|--------|-------|
| TF-IDF chunk scoring | FALLBACK | Works without ChromaDB, clearly labelled |
| ChromaDB vector store | REAL | Requires `chromadb` + `sentence-transformers` packages |
| LLM answer generation | REAL | Uses Ollama when available |

### OCR — `backend/services/ocr_service.py`

**Always REAL.** Uses `pypdf` for PDF extraction and `pytesseract` for image OCR. No AI model involved — just text extraction and chunking.

---

## Environment Variables

| Variable | Controls |
|----------|----------|
| `APP_MODE` | Global switch: `demo` = all fallbacks, `real` = attempt real services |
| `OLLAMA_ENABLED` | Whether to call Ollama daemon for LLM tasks |
| `BHASHINI_USER_ID/API_KEY/PIPELINE_ID` | Bhashini cloud NMT credentials |
| `VOSK_ASR_MODEL_DIR` | Path to Vosk Hindi ASR model |
| `CHROMA_PERSIST_DIR` | ChromaDB persistence directory |

---

## No Fake Implementations

Every AI component either:
1. Calls a real model/service when configured, **OR**
2. Returns a deterministic fallback clearly labelled as `mode: "fallback"` or `mode: "demo"`

No component ever claims `mode: "real"` when it is using fallback logic. The frontend reads these mode labels to display honest AI status indicators to the teacher.
