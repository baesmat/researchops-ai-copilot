from __future__ import annotations

from app.models.analysis import DocumentChunk
from app.services.evidence_retriever import BM25Index


def _chunks(*texts: str) -> list[DocumentChunk]:  # type: ignore[valid-type]
    return [
        DocumentChunk(chunk_id=f"d-p1-c{i}", doc_id="d", text=t, page=1, section="S")
        for i, t in enumerate(texts)
    ]


def test_relevant_chunk_ranks_first():
    chunks = _chunks(
        "The study plans enrollment of 120 participants across two sites.",
        "Imaging is performed every six weeks with contrast CT.",
        "Safety monitoring is performed by an independent committee.",
    )
    index = BM25Index(chunks)
    hits = index.search("planned enrollment participants", top_k=2)
    assert hits[0].chunk.chunk_id == "d-p1-c0"
    assert hits[0].score > 0


def test_no_match_returns_empty():
    index = BM25Index(_chunks("Alpha beta gamma."))
    assert index.search("delta epsilon zeta") == []
    assert BM25Index([]).search("anything") == []


def test_chunk_lookup_by_id():
    chunks = _chunks("First chunk text.", "Second chunk about imaging MRI scans.")
    index = BM25Index(chunks)
    assert index.chunk_by_id("d-p1-c1").text.startswith("Second")
    assert index.chunk_by_id("missing") is None


def test_deterministic_ranking():
    chunks = _chunks("Enrollment is one hundred twenty.", "Imaging monthly.", "More enrollment text.")
    a = BM25Index(chunks).search("enrollment", top_k=3)
    b = BM25Index(chunks).search("enrollment", top_k=3)
    assert [s.chunk.chunk_id for s in a] == [s.chunk.chunk_id for s in b]
