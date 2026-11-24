import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, rag  # noqa: E402
from pdf_maker import make_pdf  # noqa: E402

REPORT = make_pdf([
    "PaperTrail annual report. The company builds a study tool for students.",
    "Revenue grew by 12 percent in 2024 because of the new cloud product.",
    "The team hired five new engineers in Cork during the summer.",
])


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)   # never call a real LLM in tests
    app = create_app({
        "TESTING": True,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "CHUNKS_FOLDER": str(tmp_path / "chunks"),
        "INGEST_SYNC": True,   # read the PDF inside the request, so tests don't wait
    })
    from app import auth
    from app.routes import jobs
    for store in (jobs, auth.users, auth.users_by_email, auth.users_by_phone, auth.tokens):
        store.clear()  # start each test with empty stores
    return app.test_client()


def signup(client, **overrides):
    body = {
        "first_name": "Ali",
        "last_name": "Rizvi",
        "email": "ali@example.com",
        "phone": "",
        "password": "secret123",
    }
    body.update(overrides)
    return client.post("/auth/register", json=body)


def auth_header(client, **overrides):
    token = signup(client, **overrides).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def upload(client, headers, name="notes.pdf", content=b"%PDF-1.4 fake pdf"):
    data = {"file": (io.BytesIO(content), name)}
    return client.post("/upload", data=data, content_type="multipart/form-data", headers=headers)


# ---------- Health ----------

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


# ---------- Accounts ----------

def test_register_and_me(client):
    res = signup(client)
    assert res.status_code == 201
    data = res.get_json()
    assert data["user"]["first_name"] == "Ali"
    assert "password_hash" not in data["user"]

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {data['token']}"})
    assert res.status_code == 200
    assert res.get_json()["email"] == "ali@example.com"


def test_register_rejects_bad_input(client):
    assert signup(client, first_name="").status_code == 400                 # missing name
    assert signup(client, email="", phone="").status_code == 400            # no email or phone
    assert signup(client, email="not-an-email").status_code == 400          # bad email
    assert signup(client, email="", phone="12ab").status_code == 400        # bad phone
    assert signup(client, password="1234567").status_code == 400            # too short
    assert signup(client).status_code == 201
    assert signup(client).status_code == 409                                # email taken


def test_register_with_phone_only(client):
    res = signup(client, email="", phone="+353 87 123 4567")
    assert res.status_code == 201
    assert res.get_json()["user"]["phone"] == "+353871234567"


def test_password_is_not_stored_as_plain_text(client):
    signup(client)
    from app.auth import users
    user = next(iter(users.values()))
    assert user["password_hash"] != "secret123"


def test_login_with_email_or_phone_and_logout(client):
    signup(client, phone="+91 98765 43210")
    wrong = client.post("/auth/login", json={"identifier": "ali@example.com", "password": "wrong-pass"})
    assert wrong.status_code == 401

    by_email = client.post("/auth/login", json={"identifier": "ALI@example.com", "password": "secret123"})
    assert by_email.status_code == 200
    by_phone = client.post("/auth/login", json={"identifier": "+919876543210", "password": "secret123"})
    assert by_phone.status_code == 200

    headers = {"Authorization": f"Bearer {by_email.get_json()['token']}"}
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401   # token no longer works


# ---------- Protected routes ----------

def test_routes_need_login(client):
    assert upload(client, headers={}).status_code == 401
    assert client.get("/jobs").status_code == 401
    assert client.post("/ask", json={"question": "hi"}).status_code == 401


def test_upload_pdf_and_check_status(client):
    headers = auth_header(client)
    res = upload(client, headers)
    assert res.status_code == 202
    job = res.get_json()
    assert job["status"] == "queued"
    assert job["owner"]

    res = client.get(f"/status/{job['job_id']}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["filename"] == "notes.pdf"


def test_upload_rejects_non_pdf(client):
    headers = auth_header(client)
    assert upload(client, headers, name="notes.txt", content=b"hello").status_code == 400


def test_upload_without_file(client):
    headers = auth_header(client)
    res = client.post("/upload", data={}, content_type="multipart/form-data", headers=headers)
    assert res.status_code == 400


def test_unknown_job(client):
    headers = auth_header(client)
    assert client.get("/status/does-not-exist", headers=headers).status_code == 404


def test_users_only_see_their_own_documents(client):
    ali = auth_header(client)
    sara = auth_header(client, first_name="Sara", email="sara@example.com")
    job = upload(client, ali).get_json()

    assert len(client.get("/jobs", headers=ali).get_json()) == 1
    assert client.get("/jobs", headers=sara).get_json() == []
    assert client.get(f"/status/{job['job_id']}", headers=sara).status_code == 404


def test_jobs_list_and_cors(client):
    headers = auth_header(client)
    upload(client, headers, name="a.pdf")
    res = client.get("/jobs", headers=headers)
    assert res.status_code == 200
    assert len(res.get_json()) == 1
    assert "Authorization" in res.headers["Access-Control-Allow-Headers"]


def test_ask_validates_input(client):
    headers = auth_header(client)
    assert client.post("/ask", json={}, headers=headers).status_code == 400                       # no question
    assert client.post("/ask", json={"question": "hi"}, headers=headers).status_code == 400       # no doc_id
    long_question = {"doc_id": "x", "question": "a" * 1001}
    assert client.post("/ask", json=long_question, headers=headers).status_code == 400
    missing = client.post("/ask", json={"doc_id": "nope", "question": "hi"}, headers=headers)
    assert missing.status_code == 404


# ---------- RAG: upload -> read -> ask ----------

def test_real_pdf_is_read_after_upload(client, tmp_path):
    headers = auth_header(client)
    job = upload(client, headers, name="report.pdf", content=REPORT).get_json()
    assert job["status"] == "queued"
    assert "path" not in job                           # server file path stays private

    job = client.get(f"/status/{job['job_id']}", headers=headers).get_json()
    assert job["status"] == "done"
    assert job["pages"] == 3
    assert job["chunks"] == 3
    assert (tmp_path / "chunks" / f"{job['doc_id']}.jsonl").exists()


def test_broken_pdf_fails_with_a_message(client):
    headers = auth_header(client)
    job = upload(client, headers).get_json()           # b"%PDF-1.4 fake pdf"
    job = client.get(f"/status/{job['job_id']}", headers=headers).get_json()
    assert job["status"] == "failed"
    assert job["error"]

    res = client.post("/ask", json={"doc_id": job["doc_id"], "question": "hi"}, headers=headers)
    assert res.status_code == 409


def test_pdf_without_text_fails_with_ocr_message(client):
    headers = auth_header(client)
    job = upload(client, headers, name="scan.pdf", content=make_pdf([""])).get_json()
    job = client.get(f"/status/{job['job_id']}", headers=headers).get_json()
    assert job["status"] == "failed"
    assert "OCR" in job["error"]


def test_ask_without_llm_returns_matching_passages(client):
    headers = auth_header(client)
    doc_id = upload(client, headers, name="report.pdf", content=REPORT).get_json()["doc_id"]

    res = client.post("/ask", json={"doc_id": doc_id, "question": "How much did revenue grow?"}, headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["question"] == "How much did revenue grow?"
    assert data["sources"][0]["page"] == 2
    assert "12 percent" in data["sources"][0]["text"]


def test_ask_with_llm(client, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(rag, "call_llm", lambda messages: "It grew by 12 percent (p. 2).")
    headers = auth_header(client)
    doc_id = upload(client, headers, name="report.pdf", content=REPORT).get_json()["doc_id"]

    body = {"doc_id": doc_id, "question": "How much did revenue grow?",
            "history": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]}
    data = client.post("/ask", json=body, headers=headers).get_json()
    assert data["answer"] == "It grew by 12 percent (p. 2)."
    assert [s["page"] for s in data["sources"]] == [2]


def test_ask_question_not_in_document(client):
    headers = auth_header(client)
    doc_id = upload(client, headers, name="report.pdf", content=REPORT).get_json()["doc_id"]
    data = client.post("/ask", json={"doc_id": doc_id, "question": "quantum chromodynamics"},
                       headers=headers).get_json()
    assert data["answer"] == rag.NOT_FOUND
    assert data["sources"] == []


def test_llm_failure_returns_502(client, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")

    def broken(messages):
        raise rag.LLMError("timeout")

    monkeypatch.setattr(rag, "call_llm", broken)
    headers = auth_header(client)
    doc_id = upload(client, headers, name="report.pdf", content=REPORT).get_json()["doc_id"]
    res = client.post("/ask", json={"doc_id": doc_id, "question": "revenue"}, headers=headers)
    assert res.status_code == 502
    assert res.get_json()["error"] == "timeout"   # the real reason reaches the chat


def test_cannot_ask_about_someone_elses_document(client):
    ali = auth_header(client)
    sara = auth_header(client, first_name="Sara", email="sara@example.com")
    doc_id = upload(client, ali, name="report.pdf", content=REPORT).get_json()["doc_id"]
    res = client.post("/ask", json={"doc_id": doc_id, "question": "revenue"}, headers=sara)
    assert res.status_code == 404


def test_ask_while_document_is_still_being_read(client):
    from app.routes import jobs
    headers = auth_header(client)
    job = upload(client, headers, name="report.pdf", content=REPORT).get_json()
    jobs[job["job_id"]]["status"] = "processing"
    res = client.post("/ask", json={"doc_id": job["doc_id"], "question": "revenue"}, headers=headers)
    assert res.status_code == 409


# ---------- Deleting documents ----------

def test_delete_document_removes_files(client, tmp_path):
    headers = auth_header(client)
    job = upload(client, headers, name="report.pdf", content=REPORT).get_json()
    doc_id = job["doc_id"]

    sara = auth_header(client, first_name="Sara", email="sara@example.com")
    assert client.delete(f"/docs/{doc_id}", headers=sara).status_code == 404   # not hers

    assert client.delete(f"/docs/{doc_id}", headers=headers).status_code == 200
    assert client.get("/jobs", headers=headers).get_json() == []
    assert list((tmp_path / "uploads").iterdir()) == []
    assert list((tmp_path / "chunks").iterdir()) == []
    assert client.delete(f"/docs/{doc_id}", headers=headers).status_code == 404


def test_cors_allows_delete(client):
    res = client.get("/health")
    assert "DELETE" in res.headers["Access-Control-Allow-Methods"]
