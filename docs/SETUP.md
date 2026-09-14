# Setup Guide

Step-by-step instructions for running BhashaSetu on Windows (or Linux/Mac).

---

## Prerequisites

- **Python 3.11+** (check: `python --version`)
- **pip** (check: `pip --version`)
- **Git** (check: `git --version`)
- **Tesseract OCR** (optional, for textbook image upload)
  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
  - Linux: `sudo apt install tesseract-ocr`
  - Mac: `brew install tesseract`

## 1. Clone & Setup

```bash
git clone https://github.com/your-org/bhashasetu.git
cd bhashasetu

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate          # Windows PowerShell
# source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure Environment

```bash
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
```

Edit `.env` if needed. The defaults work for demo mode out of the box.

## 3. Run the Application

```bash
python -m backend.app
```

Open `http://localhost:5000` in your browser.

## 4. Demo Login

| Field | Value |
|-------|-------|
| Teacher ID | `T-1001` |
| Password | `demo1234` |

The app auto-seeds demo data on first run.

---

## Optional: Enable Real AI Services

### Ollama (Local LLM)

```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5:3b-instruct
```

Then in `.env`:
```
APP_MODE=real
OLLAMA_ENABLED=true
```

### Vosk (Offline Hindi ASR)

1. Download `vosk-model-small-hi-0.22` from https://alphacephei.com/vosk/models
2. Extract into `models/vosk-model-small-hi-0.22/`
3. Set `APP_MODE=real` in `.env`

### Bhashini (Cloud NMT)

Register at https://dashboard.bhashini.co.in and add credentials to `.env`:
```
BHASHINI_USER_ID=your-user-id
BHASHINI_API_KEY=your-api-key
BHASHINI_PIPELINE_ID=your-pipeline-id
```

### NLLB-200 (Local Neural MT)

```bash
pip install transformers torch
```

The model auto-downloads on first real translation (~1.2GB). No additional config needed.

### ChromaDB (Vector Store for RAG)

```bash
pip install chromadb sentence-transformers
```

Set `APP_MODE=real` in `.env`.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'backend'` | Run from project root, not from inside `backend/` |
| Port 5000 in use | Change `FLASK_PORT` in `.env` |
| Ollama timeout | Ensure Ollama is running: `ollama serve` |
| Tesseract not found | Add Tesseract to PATH or set `TESSERACT_CMD` env var |
| NLLB import error | Install: `pip install transformers torch` |
