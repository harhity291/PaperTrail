# PaperTrail – Backend (Flask)

Flask API for PaperTrail: user accounts, PDF uploads, and question answering over each PDF with RAG.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Check the server is running |
| POST | `/upload` | Upload a PDF (form field `file`). Saves it and returns a `job_id` and `doc_id` |
| GET | `/status/<job_id>` | Get the status of an upload job: `queued` → `processing` → `done` / `failed` |
| GET | `/jobs` | The logged-in user's documents, newest first |
| POST | `/ask` | Ask about a document: `{"doc_id", "question", "history"}` → `{"answer", "sources"}` |
| DELETE | `/docs/<doc_id>` | Delete a document, its PDF and its chunks |

Everything except `/health` and `/auth/register`, `/auth/login` needs `Authorization: Bearer <token>`.

## How the RAG pipeline works (`app/rag.py`)

1. **Ingest** (runs in a background thread after upload): pdfplumber reads each page → text is split into 200-word chunks with a 40-word overlap → saved to `data/chunks/<doc_id>.jsonl`. Each chunk keeps its page number.
2. **Retrieve**: the question is scored against every chunk with BM25 (keyword ranking). The best 4 chunks are kept. If nothing matches, the answer is "I couldn't find anything about that in this document" and the LLM is not called.
3. **Answer**: the chunks, the question and the last few chat messages go to the LLM, which is told to answer only from the passages and cite pages like (p. 4). The response includes the passages used (`sources`), so the frontend can show them.

## LLM setup

Any LLM with an OpenAI-compatible API works (Groq, OpenAI, Ollama on your laptop, ...).

```bash
cp .env.example .env     # then paste your API key into .env
```

Without `LLM_MODEL` set, `/ask` still works: it returns the best-matching passages instead of a written answer.

## Run it

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Try it:

```bash
curl http://localhost:5001/health
# register, then use the token it returns
curl -X POST http://localhost:5001/auth/register -H "Content-Type: application/json" \
     -d '{"first_name":"Ali","last_name":"Rizvi","email":"ali@example.com","password":"secret123"}'
curl -H "Authorization: Bearer <token>" -F "file=@sample.pdf" http://localhost:5001/upload
curl -H "Authorization: Bearer <token>" http://localhost:5001/status/<job_id>
curl -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
     -d '{"doc_id":"<doc_id>","question":"What is the main conclusion?"}' http://localhost:5001/ask
```

Run tests: `pytest`

## Next steps

- [x] Extract PDF text with pdfplumber, chunk it, save chunks to `data/chunks/<doc_id>.jsonl`
- [x] BM25 retrieval + LLM answers with page citations (`POST /ask`)
- [ ] Replace the in-memory job store and background thread with Redis (HASH for job data, LIST as a FIFO queue) and a worker process
- [ ] Store users, jobs and chunks in the database instead of memory / JSONL files
- [ ] Embedding (vector) search alongside BM25, for questions that use different words from the PDF
