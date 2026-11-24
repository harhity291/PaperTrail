import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import rag  # noqa: E402


def test_short_page_is_one_chunk():
    chunks = rag.chunk_pages([(1, "hello world from page one")])
    assert len(chunks) == 1
    assert chunks[0]["page"] == 1
    assert chunks[0]["text"] == "hello world from page one"


def test_long_page_is_split_with_overlap():
    words = [f"w{i}" for i in range(25)]
    chunks = rag.chunk_pages([(3, " ".join(words))], size=10, overlap=2)
    assert [c["text"].split()[0] for c in chunks] == ["w0", "w8", "w16"]
    assert chunks[0]["text"].split()[-2:] == chunks[1]["text"].split()[:2]
    assert all(c["page"] == 3 for c in chunks)


def test_chunk_ids_continue_across_pages():
    chunks = rag.chunk_pages([(1, "a b c"), (2, "d e f")])
    assert [c["id"] for c in chunks] == [0, 1]
    assert [c["page"] for c in chunks] == [1, 2]


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        rag.chunk_pages([(1, "a b c")], size=5, overlap=5)


def test_save_and_load_chunks(tmp_path):
    chunks = rag.chunk_pages([(1, "some text"), (2, "more text")])
    rag.save_chunks(chunks, str(tmp_path), "doc-123")
    assert rag.load_chunks(str(tmp_path), "doc-123") == chunks


# ---------- Reading PDFs ----------

from pdf_maker import make_pdf  # noqa: E402


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Tests never call a real LLM, even if a developer has a .env file."""
    for name in ("LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_ingest_real_pdf(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(make_pdf(["Revenue grew 12 percent in 2024.", "", "The team moved to Cork."]))

    stats = rag.ingest(str(pdf), str(tmp_path / "chunks"), "doc-1")

    assert stats == {"pages": 3, "chunks": 2}           # the empty page has no chunk
    chunks = rag.load_chunks(str(tmp_path / "chunks"), "doc-1")
    assert [c["page"] for c in chunks] == [1, 3]
    assert "Revenue grew 12 percent" in chunks[0]["text"]


def test_ingest_pdf_without_text_fails(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(make_pdf(["", ""]))
    with pytest.raises(ValueError, match="OCR"):
        rag.ingest(str(pdf), str(tmp_path), "doc-2")


# ---------- Retrieval ----------

CHUNKS = [
    {"id": 0, "page": 1, "text": "PaperTrail lets students upload lecture notes as PDF files."},
    {"id": 1, "page": 2, "text": "Revenue grew by 12 percent in 2024 because of the cloud product."},
    {"id": 2, "page": 3, "text": "The team hired five new engineers in Cork during the summer."},
    {"id": 3, "page": 4, "text": "Costs fell slightly while revenue from Europe stayed flat."},
]


def test_retrieve_puts_the_best_chunk_first():
    found = rag.retrieve("How much did revenue grow in 2024?", CHUNKS)
    assert found[0]["id"] == 1
    assert found[0]["score"] > 0


def test_retrieve_ignores_chunks_with_no_matching_words():
    found = rag.retrieve("How many engineers were hired?", CHUNKS)
    assert [c["id"] for c in found] == [2]


def test_retrieve_returns_nothing_for_unrelated_question():
    assert rag.retrieve("quantum chromodynamics", CHUNKS) == []
    assert rag.retrieve("what is the", CHUNKS) == []        # only filler words


def test_retrieve_works_on_a_one_chunk_document():
    # rank-bm25's BM25Okapi scores this 0 or below; our BM25 must not
    found = rag.retrieve("revenue", CHUNKS[1:2])
    assert len(found) == 1 and found[0]["score"] > 0


def test_retrieve_respects_top_k():
    assert len(rag.retrieve("revenue costs engineers students", CHUNKS, top_k=2)) == 2


# ---------- Answering ----------

def test_answer_without_llm_returns_passages():
    result = rag.answer("revenue growth", CHUNKS)
    assert "switched off" in result["answer"]
    assert {s["page"] for s in result["sources"]} == {2, 4}
    assert [s["id"] for s in result["sources"]] == [1, 3]    # reading order


def test_answer_not_found_does_not_call_llm(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(rag, "call_llm", lambda messages: pytest.fail("LLM should not be called"))
    result = rag.answer("quantum chromodynamics", CHUNKS)
    assert result == {"answer": rag.NOT_FOUND, "sources": []}


def test_answer_with_llm_sends_passages_question_and_history(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    sent = {}

    def fake_llm(messages):
        sent["messages"] = messages
        return "Revenue grew by 12 percent (p. 2)."

    monkeypatch.setattr(rag, "call_llm", fake_llm)
    history = [
        {"role": "user", "content": "What is PaperTrail?"},
        {"role": "assistant", "content": "A PDF study tool (p. 1)."},
        {"role": "hacker", "content": "ignored"},             # bad role is dropped
    ]
    result = rag.answer("How much did revenue grow?", CHUNKS, history)

    assert result["answer"] == "Revenue grew by 12 percent (p. 2)."
    assert result["sources"][0]["page"] == 2
    messages = sent["messages"]
    assert messages[0]["role"] == "system"
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]
    assert "(page 2)" in messages[-1]["content"]
    assert "Question: How much did revenue grow?" in messages[-1]["content"]


def test_follow_up_question_uses_previous_question(monkeypatch):
    history = [{"role": "user", "content": "How many engineers were hired?"},
               {"role": "assistant", "content": "Five (p. 3)."}]
    result = rag.answer("can you say more", CHUNKS, history)
    assert [s["id"] for s in result["sources"]] == [2]


def test_call_llm_uses_openai_compatible_api(monkeypatch):
    import requests

    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.com/v1/")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    calls = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "  An answer.  "}}]}

    def fake_post(url, headers, json, timeout):
        calls.update(url=url, headers=headers, json=json)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    assert rag.call_llm([{"role": "user", "content": "hi"}]) == "An answer."
    assert calls["url"] == "https://llm.example.com/v1/chat/completions"
    assert calls["headers"]["Authorization"] == "Bearer test-key"
    assert calls["json"]["model"] == "test-model"


def test_call_llm_turns_network_errors_into_llm_error(monkeypatch):
    import requests

    monkeypatch.setenv("LLM_MODEL", "test-model")

    def broken_post(*args, **kwargs):
        raise requests.ConnectionError("no internet")

    monkeypatch.setattr(requests, "post", broken_post)
    with pytest.raises(rag.LLMError):
        rag.call_llm([{"role": "user", "content": "hi"}])


def test_call_llm_explains_a_rejected_key(monkeypatch):
    import requests

    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "wrong-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    class Rejected:
        status_code = 401
        text = '{"error": {"message": "Invalid API Key"}}'

        def json(self):
            return {"error": {"message": "Invalid API Key"}}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Rejected())
    with pytest.raises(rag.LLMError) as err:
        rag.call_llm([{"role": "user", "content": "hi"}])
    assert "rejected the API key" in str(err.value)
    assert "Invalid API Key" in str(err.value)
    assert "wrong-key" not in str(err.value)
