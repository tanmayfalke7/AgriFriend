# AgriVoice AI

A minimal voice-first multilingual agricultural assistant for local
demonstrations. It retrieves approved PDF evidence from a persistent ChromaDB
collection, then uses Gemini only when its transparent relevance gate passes.
English, Hindi, and Marathi are supported.

## Included

- FastAPI backend and responsive HTML/CSS/vanilla-JS interface at one URL
- Persistent ChromaDB, PDF upload, page-aware chunking and SHA-256 deduplication
- Multilingual retrieval using `paraphrase-multilingual-MiniLM-L12-v2`
- Guarded Gemini RAG, browser recording/upload, Faster-Whisper, and Edge TTS
- MySQL SQLAlchemy models for documents, query logs, and feedback
- Health endpoint and graceful MySQL/Gemini failure handling

## Layout

```
backend/app/          FastAPI application, retrieval, database and voice services
frontend/             Browser application
data/chroma_db/       Persistent local vectors (generated)
data/uploads/         Uploaded PDFs (generated)
data/generated_audio/ Generated MP3 files (generated)
scripts/              Initial PDF indexer and retrieval verifier
tests/                Basic unit checks
```

## Windows PowerShell setup

```powershell
cd C:\Users\tanma\OneDrive\Desktop\AgriFriend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
mysql -u root -p < setup.sql
python scripts/create_embeddings.py Washim.pdf
cd backend
uvicorn app.main:app --reload
```

Edit `.env` and set `GEMINI_API_KEY` plus the `MYSQL_*` values. Do not commit
`.env`. The local application is available at <http://127.0.0.1:8000> and API
documentation at <http://127.0.0.1:8000/docs>.

## Ubuntu/WSL

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd backend && uvicorn app.main:app --reload
```

Install FFmpeg for audio conversion if required: `sudo apt install ffmpeg` on
Ubuntu or `winget install Gyan.FFmpeg` on Windows.

## Limitations

`Washim.pdf` is a 2011 contingency-plan source, not current live information.
No live weather, market price, or government-scheme feeds are connected. The
retrieval threshold is a heuristic (`RETRIEVAL_DISTANCE_THRESHOLD`), not a
calibrated confidence score: weak or absent evidence always produces a safe
refusal. MySQL is optional for basic chat/retrieval but required for saved logs
and feedback.
