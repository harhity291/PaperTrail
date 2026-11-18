"""RAG (Retrieval-Augmented Generation) pipeline for PaperTrail.

STATUS: WORK IN PROGRESS - not connected to the API yet.

Done so far:
  - extract_pages(): read the text of a PDF, page by page (pdfplumber)
  - chunk_pages():   split page text into overlapping chunks
  - save_chunks() / load_chunks(): store chunks in data/chunks/<doc_id>.jsonl

Still to do:
  - TODO: retrieve()  - rank chunks for a question with BM25 (rank-bm25)
  - TODO: answer()    - send the top chunks + question to the LLM
  - TODO: call ingest() from the upload job (queued -> processing -> done)
  - TODO: connect answer() to POST /ask in routes.py
"""
import json
import os

CHUNK_SIZE = 200     # words per chunk
CHUNK_OVERLAP = 40   # words shared between neighbouring chunks


def extract_pages(pdf_path):
    """Return a list of (page_number, text) for every page that has text."""
    import pdfplumber  # imported here so the rest of the module works without it

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((number, text))
    return pages


def chunk_pages(pages, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split (page_number, text) pairs into overlapping word chunks.

    Each chunk remembers its page, so answers can cite where they came from.
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks = []
    step = size - overlap
    for page_number, text in pages:
        words = text.split()
        for start in range(0, len(words), step):
            piece = words[start:start + size]
            chunks.append({
                "id": len(chunks),
                "page": page_number,
                "text": " ".join(piece),
            })
            if start + size >= len(words):
                break
    return chunks


def chunks_path(chunks_dir, doc_id):
    return os.path.join(chunks_dir, f"{doc_id}.jsonl")


def save_chunks(chunks, chunks_dir, doc_id):
    """Write one JSON object per line to data/chunks/<doc_id>.jsonl."""
    os.makedirs(chunks_dir, exist_ok=True)
    path = chunks_path(chunks_dir, doc_id)
    with open(path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    return path


def load_chunks(chunks_dir, doc_id):
    path = chunks_path(chunks_dir, doc_id)
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def ingest(pdf_path, chunks_dir, doc_id):
    """PDF -> pages -> chunks -> saved file. Returns the number of chunks."""
    chunks = chunk_pages(extract_pages(pdf_path))
    save_chunks(chunks, chunks_dir, doc_id)
    return len(chunks)


def retrieve(question, chunks, top_k=3):
    """TODO: return the top_k chunks most relevant to the question (BM25)."""
    raise NotImplementedError("Retrieval is not built yet")


def answer(question, chunks):
    """TODO: build a prompt from the retrieved chunks and call the LLM."""
    raise NotImplementedError("Answer generation is not built yet")
