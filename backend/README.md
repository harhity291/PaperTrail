# PaperTrail – Backend (Flask)

First step of the backend: a Flask API that accepts PDF uploads and tracks an ingestion job for each one.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Check the server is running |
| POST | `/upload` | Upload a PDF (form field `file`). Saves it and returns a `job_id` and `doc_id` |
| GET | `/status/<job_id>` | Get the status of an upload job |

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
curl -F "file=@sample.pdf" http://localhost:5001/upload
curl http://localhost:5001/status/<job_id>
```

Run tests: `pytest`

## Next steps

- [ ] Replace the in-memory job store with Redis (HASH for job data, LIST as a FIFO queue)
- [ ] Worker process: extract PDF text with pdfplumber
- [ ] Chunk text and save chunks to `data/chunks/<doc_id>.jsonl`
- [ ] `GET /docs/<doc_id>/chunks` endpoint
