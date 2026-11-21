"""API routes for PaperTrail."""
import os
import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.utils import secure_filename

from . import rag
from .auth import login_required

bp = Blueprint("api", __name__)

MAX_QUESTION_LENGTH = 1000

# Temporary in-memory job store.
# Plan: replace with a Redis HASH + LIST queue (see project README).
jobs = {}


def is_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"


def find_my_doc(doc_id):
    """The logged-in user's job for doc_id, or None."""
    for job in jobs.values():
        if job["doc_id"] == doc_id and job["owner"] == g.user["id"]:
            return job
    return None


def process_document(job_id, pdf_path, chunks_dir, logger):
    """Read the PDF and save its chunks: queued -> processing -> done / failed.

    Runs in a background thread so the upload request returns straight away.
    Plan: move this into a Redis worker process (see project README).
    """
    job = jobs.get(job_id)
    if job is None:
        return
    job["status"] = "processing"
    try:
        stats = rag.ingest(pdf_path, chunks_dir, job["doc_id"])
    except ValueError as err:           # e.g. no text in the PDF
        job.update(status="failed", error=str(err))
        return
    except Exception:                   # broken or unreadable PDF
        logger.exception("Could not read %s", pdf_path)
        job.update(status="failed", error="Could not read this PDF. Is it a valid PDF file?")
        return

    if job_id not in jobs:              # deleted while we were reading it
        remove_file(rag.chunks_path(chunks_dir, job["doc_id"]))
        return
    job.update(status="done", pages=stats["pages"], chunks=stats["chunks"])


def remove_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "papertrail-backend"})


@bp.post("/upload")
@login_required
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part. Send the PDF in a form field called 'file'."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400
    if not is_pdf(file.filename):
        return jsonify({"error": "Only PDF files are allowed."}), 400

    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"{doc_id}_{filename}")
    file.save(save_path)

    jobs[job_id] = {
        "job_id": job_id,
        "doc_id": doc_id,
        "owner": g.user["id"],  # each user only sees their own documents
        "filename": filename,
        "size_bytes": os.path.getsize(save_path),
        "status": "queued",  # then: processing -> done / failed
        "created_at": datetime.now(timezone.utc).isoformat(),
        "path": save_path,
    }
    response = public_job(jobs[job_id])  # copy now, before the worker changes the status

    args = (job_id, save_path, current_app.config["CHUNKS_FOLDER"], current_app.logger)
    if current_app.config.get("INGEST_SYNC"):
        process_document(*args)
    else:
        threading.Thread(target=process_document, args=args, daemon=True).start()

    return jsonify(response), 202


def public_job(job):
    """Job data for the frontend (the file path on the server stays private)."""
    return {k: v for k, v in job.items() if k != "path"}


@bp.get("/status/<job_id>")
@login_required
def status(job_id):
    job = jobs.get(job_id)
    if job is None or job["owner"] != g.user["id"]:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(public_job(job))


@bp.get("/jobs")
@login_required
def list_jobs():
    """The logged-in user's upload jobs, newest first."""
    my_jobs = [public_job(j) for j in jobs.values() if j["owner"] == g.user["id"]]
    my_jobs.sort(key=lambda j: j["created_at"], reverse=True)
    return jsonify(my_jobs)


@bp.delete("/docs/<doc_id>")
@login_required
def delete_doc(doc_id):
    """Delete a document: its job, the uploaded PDF and its chunks."""
    job = find_my_doc(doc_id)
    if job is None:
        return jsonify({"error": "Document not found."}), 404
    jobs.pop(job["job_id"], None)
    remove_file(job["path"])
    remove_file(rag.chunks_path(current_app.config["CHUNKS_FOLDER"], doc_id))
    return jsonify({"message": "Document deleted.", "doc_id": doc_id})


@bp.post("/ask")
@login_required
def ask():
    """Answer a question about one of the user's documents.

    Send:    {"doc_id": "...", "question": "...", "history": [{"role", "content"}, ...]}
    Returns: {"question", "answer", "sources": [{"id", "page", "text", "score"}]}
    """
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    doc_id = (body.get("doc_id") or "").strip()

    if not question:
        return jsonify({"error": "Send JSON like {\"doc_id\": \"...\", \"question\": \"...\"}."}), 400
    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({"error": f"Questions must be {MAX_QUESTION_LENGTH} characters or fewer."}), 400
    if not doc_id:
        return jsonify({"error": "Choose a document to ask about."}), 400

    job = find_my_doc(doc_id)
    if job is None:
        return jsonify({"error": "Document not found."}), 404
    if job["status"] == "failed":
        return jsonify({"error": job.get("error") or "This document could not be read."}), 409
    if job["status"] != "done":
        return jsonify({"error": "This document is still being read. Try again in a moment."}), 409

    history = body.get("history") if isinstance(body.get("history"), list) else []
    try:
        chunks = rag.load_chunks(current_app.config["CHUNKS_FOLDER"], doc_id)
    except FileNotFoundError:
        return jsonify({"error": "This document's text is missing. Please upload it again."}), 409
    try:
        result = rag.answer(question, chunks, history)
    except rag.LLMError:
        current_app.logger.exception("LLM call failed")
        return jsonify({"error": "The AI service didn't respond. Please try again in a moment."}), 502

    return jsonify({"question": question, **result})


@bp.app_errorhandler(413)
def too_large(_error):
    return jsonify({"error": "File is too large (max 20 MB)."}), 413
