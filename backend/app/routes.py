"""API routes for PaperTrail."""
import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.utils import secure_filename

from .auth import login_required

bp = Blueprint("api", __name__)

# Temporary in-memory job store.
# Plan: replace with a Redis HASH + LIST queue (see project README).
jobs = {}


def is_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"


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
        "status": "queued",  # later: queued -> processing -> done / failed
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return jsonify(jobs[job_id]), 202


@bp.get("/status/<job_id>")
@login_required
def status(job_id):
    job = jobs.get(job_id)
    if job is None or job["owner"] != g.user["id"]:
        return jsonify({"error": "Job not found."}), 404
    return jsonify(job)


@bp.get("/jobs")
@login_required
def list_jobs():
    """The logged-in user's upload jobs, newest first."""
    my_jobs = [j for j in jobs.values() if j["owner"] == g.user["id"]]
    my_jobs.sort(key=lambda j: j["created_at"], reverse=True)
    return jsonify(my_jobs)


@bp.post("/ask")
@login_required
def ask():
    """Placeholder for the question endpoint (not built yet)."""
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Send JSON like {\"question\": \"...\"}."}), 400
    return jsonify({
        "question": question,
        "answer": None,
        "message": "Answering questions is coming soon. For now your document is saved and queued.",
    }), 501


@bp.app_errorhandler(413)
def too_large(_error):
    return jsonify({"error": "File is too large (max 20 MB)."}), 413
