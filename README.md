# PaperTrail
An AI-powered PDF chatbot using Retrieval-Augmented Generation (RAG) and Large Language Models (LLMs) to understand documents and provide context-aware answers to user queries.

## Architecture (current)


                 ┌─────────────┐   POST /upload (multipart PDF)
      client ───►│  Flask API  │───► save to data/uploads/
                 │ app/server  │───► create job HASH + LPUSH id  ┐
                 └─────────────┘                                 │  Redis
                        ▲  GET /status/<job_id>                  │  LIST = FIFO queue
                        │  GET /docs/<doc_id>/chunks             │
                        │                                        ▼
                 ┌──────┴───────────────────────────────────────────┐
                 │  worker (separate process)  ingestion/worker.py   │
                 │    BRPOP job id                                   │
                 │      → extract_pdf()   (pdfplumber: text+tables)  │
                 │      → chunk_document() (recursive, token-based)  │
                 │      → write_chunks()   data/chunks/<doc>.jsonl   │
                 └───────────────────────────────────────────────────┘

