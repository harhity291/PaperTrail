# PaperTrail

An AI-powered PDF chatbot. Upload a PDF, ask questions about it, and get answers taken only from that document, with page references. Built with a Flask backend, an HTML/CSS/JavaScript frontend and Retrieval-Augmented Generation (RAG).

Team project for CS6422 Complex Systems Development, University College Cork.

## What works now

- Register with first name, last name, email and/or phone, and a password (at least 8 characters); log in with email or phone; log out
- Passwords are stored as hashes (werkzeug), never as plain text
- Upload a PDF by clicking or drag-and-drop (PDF files only, max 20 MB)
- Each PDF is read in the background; its status goes `queued` → `processing` → `done` / `failed`
- Each user sees only their own documents, and can delete them
- Ask questions about the selected document: answers come only from that PDF and cite pages, e.g. (p. 4)
- "Passages used" under each answer shows the exact text the answer came from
- Follow-up questions use the earlier conversation
- If the answer is not in the PDF, the app replies "I couldn't find anything about that in this document." and the LLM is not called
- Scanned PDFs (no text) and broken PDFs fail with a clear message
- LLM problems (wrong API key, no internet, out of credits) are shown as clear error messages instead of crashing
- Server status indicator on the dashboard

## How it works

```
frontend (HTML/JS, port 8000) ──fetch + Bearer token──►  Flask API (port 5001)

POST /upload ─► save PDF to data/uploads/ ─► background thread:
                  pdfplumber reads each page
                  → 200-word chunks (40-word overlap), each keeps its page number
                  → saved to data/chunks/<doc_id>.jsonl

POST /ask ───► BM25 search over the document's chunks → best 4 chunks
                  no match → "I couldn't find anything about that in this document."
                  match    → chunks + question + recent chat → LLM → answer with page citations
```

The LLM is told to use only the passages from the PDF and to ignore any instructions written inside them, which protects against prompt injection hidden in a document.

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Check the server is running |
| POST | `/auth/register` | Create an account, returns a token |
| POST | `/auth/login` | Log in with email or phone, returns a token |
| POST | `/auth/logout` | The token stops working |
| GET | `/auth/me` | Who is logged in |
| POST | `/upload` | Upload a PDF (form field `file`), returns a `job_id` and `doc_id` |
| GET | `/status/<job_id>` | Status of one upload |
| GET | `/jobs` | The logged-in user's documents, newest first |
| POST | `/ask` | `{"doc_id", "question", "history"}` → `{"answer", "sources"}` |
| DELETE | `/docs/<doc_id>` | Delete a document, its PDF and its chunks |

Everything except `/health`, `/auth/register` and `/auth/login` needs `Authorization: Bearer <token>`. More detail and `curl` examples are in [backend/README.md](backend/README.md).

## Run it

**1. Set up the LLM**

```bash
cd backend
cp .env.example .env
```

Open `backend/.env` and paste the API key into `LLM_API_KEY`. The team uses Grok (xAI); Groq and a local Ollama model also work (see `.env.example`). Without `LLM_MODEL` set, `/ask` still works and returns the best-matching passages instead of a written answer. Never commit `.env`.

**2. Terminal 1 – backend**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 run.py
```

**3. Terminal 2 – frontend**

```bash
cd frontend
python3 -m http.server 8000
```

Open http://localhost:8000 in Chrome.

Port 5001 is used because macOS AirPlay Receiver already uses port 5000.

## Tests

```bash
cd backend
pytest
```

The automated tests cover sign-up and login, password hashing, upload checks, users seeing only their own documents, PDF reading and chunking, BM25 search, the "not in the document" answer, follow-up questions, LLM errors and deleting documents.

The full list of test cases is in the [Software Testing Report](docs/PaperTrail_Software_Testing_Report_Updated.pdf).

## Project structure

```
backend/
  app/__init__.py    Flask app setup (upload folders, 20 MB limit, CORS)
  app/auth.py        Register, log in, log out, tokens, password hashing
  app/routes.py      Upload, status, documents list, ask, delete
  app/rag.py         PDF reading, chunking, BM25 search, LLM call
  tests/             pytest tests
  run.py             Starts the server on port 5001
frontend/
  index.html, login.html, register.html, dashboard.html
  js/common.js, js/auth.js, js/dashboard.js
  css/style.css
docs/
  PaperTrail_Software_Testing_Report_Updated.pdf
```

## Known limitations and next steps

- Users, tokens and documents are kept in memory, so they reset when the server restarts. Next: store them in the database.
- PDFs are read in a background thread. Next: a Redis job queue and a separate worker process.
- Search is keyword-based (BM25). Next: add embedding (vector) search for questions that use different words from the PDF.
- CORS allows any origin for the prototype; restrict it before deploying.

## License

MIT
