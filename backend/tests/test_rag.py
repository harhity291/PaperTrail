import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
