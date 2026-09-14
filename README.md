# BhashaSetu (SIH26042)

**Multilingual Vernacular Classroom Platform** — enabling Hindi-speaking teachers to deliver lessons in Santali (Ol Chiki script) through real-time AI translation, speech recognition, and curriculum-aligned content.

Built for Smart India Hackathon 2026.

## Features

- **Real-time Translation** — Hindi ↔ Santali (Ol Chiki) ↔ English via NLLB-200, Bhashini, or fallback phrase tables
- **Speech Recognition** — Hindi ASR via Vosk (offline) with browser fallback
- **Live Classroom** — Teacher broadcasts translated content, flashcards appear in real time
- **AI Worksheet Generator** — Creates curriculum-aligned worksheets from textbook context (Ollama LLM)
- **Misconception Detection** — Classifies student errors as concept gaps, language gaps, or correct understanding
- **Assessment & Analytics** — Per-concept mastery tracking, weak concept identification, class-level reporting
- **Trilingual Dictionary** — 14-word Hindi/Santali/English dictionary with search and category filters
- **RAG Pipeline** — Retrieval-Augmented Generation from uploaded textbooks via ChromaDB + TF-IDF
- **Demo Mode** — Runs entirely offline with no external services; every AI component has a clearly labelled fallback

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, Flask 3.0, Flask-Cors |
| Storage | JSON file store (MongoDB-shaped interface) |
| LLM | Ollama (qwen2.5:3b-instruct) |
| Translation | NLLB-200 (local), Bhashini DHRUVA (cloud) |
| ASR | Vosk (offline Hindi), browser Web Speech API |
| Frontend | Vanilla JS, Tailwind CSS (CDN), Stitch-generated pages |
| Vector Store | ChromaDB (optional, for RAG) |
| OCR | pypdf, pytesseract |

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/bhashasetu.git
cd bhashasetu

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac

# 5. Run the application
python -m backend.app
```

Server starts at `http://localhost:5000`.

## Demo Login

| Field | Value |
|-------|-------|
| Teacher ID | `T-1001` |
| Password | `demo1234` |

The app seeds demo data automatically on first run (1 teacher, 30 students, 1 lesson, flashcards, worksheets, and ~27 student submissions).

## Project Structure

```
bhashasetu/
├── backend/
│   ├── app.py                  # Flask app factory + entry point
│   ├── config.py               # Environment-driven configuration
│   ├── database/
│   │   ├── json_store.py       # MongoDB-shaped JSON file store
│   │   └── seed.py             # Demo data seeding
│   ├── routes/                 # API blueprints (auth, translate, worksheets, ...)
│   ├── services/               # Business logic + AI service abstractions
│   └── utils/security.py       # Password hashing + bearer-token auth
├── frontend/
│   ├── assets/js/api.js        # Centralized frontend API layer
│   └── stitch_*/               # 7 Stitch-generated HTML pages
├── data/                       # Runtime JSON data (auto-seeded)
├── docs/
│   ├── AI_STATUS.md            # AI component status (real/fallback/mock)
│   └── SETUP.md                # Detailed setup instructions
├── models/                     # AI models (not committed, see models/README.md)
├── tests/                      # Unit tests
├── .env.example                # Environment variable template
└── requirements.txt            # Python dependencies
```

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/health` | GET | No | Health check |
| `/api/auth/login` | POST | No | Teacher login |
| `/api/auth/logout` | POST | Yes | Teacher logout |
| `/api/auth/me` | GET | Yes | Current teacher info |
| `/api/lessons` | GET/POST | Yes | List/create lessons |
| `/api/translate` | POST | Yes | Translate text |
| `/api/speech/transcribe` | POST | Yes | Transcribe audio |
| `/api/flashcards` | GET | Yes | List flashcards |
| `/api/flashcards/retrieve` | POST | Yes | Retrieve by concept |
| `/api/doubt` | POST | Yes | Full doubt pipeline |
| `/api/worksheets` | GET | Yes | List worksheets |
| `/api/worksheets/generate` | POST | Yes | AI worksheet generation |
| `/api/worksheets/submit` | POST | Yes | Submit answers |
| `/api/worksheets/evaluate` | POST | Yes | Evaluate submission |
| `/api/analytics` | GET | Yes | Class analytics |
| `/api/textbooks` | GET | Yes | List textbooks |
| `/api/textbooks/upload` | POST | Yes | Upload + OCR textbook |
| `/api/rag/ask` | POST | Yes | RAG question answering |
| `/api/dictionary` | GET | No | Trilingual dictionary |

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_ollama_service.py -v
```

## AI Components

See [docs/AI_STATUS.md](docs/AI_STATUS.md) for a detailed breakdown of which AI components are real, fallback, or mock in the current build.

## Configuration

All configuration is driven by environment variables. See `.env.example` for the full list. Key settings:

- `APP_MODE=demo` — Run with canned responses (no external services needed)
- `APP_MODE=real` — Use actual AI services (Ollama, NLLB-200, Vosk, Bhashini)

## License

Built for Smart India Hackathon 2026 (SIH26042).
