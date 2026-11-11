"""Deterministic lexical retrieval over document chunks (BM25, no deps).

Retrieval is fully deterministic: identical documents always produce
identical chunk ids and rankings, which is what makes citation validation
possible.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.models.analysis import DocumentChunk

_TOKEN = re.compile(r"[a-z0-9]+")
STOP = {
    "the", "a", "an", "of", "and", "or", "to", "in", "for", "on", "with", "at", "by",
    "is", "are", "be", "will", "shall", "this", "that", "it", "as", "from", "not",
}


def tokenize(text: str) -> list[str]:  # type: ignore[valid-type]
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass
class Scored:
    chunk: DocumentChunk
    score: float


class BM25Index:
    def __init__(self, chunks: list[DocumentChunk], k1: float = 1.5, b: float = 0.75) -> None:  # type: ignore[valid-type]
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(c.text) for c in chunks]
        self.doc_len = [len(t) for t in self.doc_tokens]
        avg = sum(self.doc_len) / max(len(self.doc_len), 1)
        self.avgdl = avg if avg else 1.0
        self.df: dict[str, int] = {}
        for tokens in self.doc_tokens:
            for term in set(tokens):
                self.df[term] = self.df.get(term, 0) + 1
        self.n = len(chunks)

    def _idf(self, term: str) -> float:  # type: ignore[valid-type]
        df = self.df.get(term, 0)
        if not df:
            return 0.0
        return math.log((self.n - df + 0.5) / df + 1.0)

    def search(self, query: str, top_k: int = 5) -> list[Scored]:  # type: ignore[valid-type]
        q_tokens = tokenize(query)
        if not q_tokens or not self.chunks:
            return []
        scores: list[float] = []
        for tokens in self.doc_tokens:
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            for qt in q_tokens:
                f = tf.get(qt, 0)
                if not f:
                    continue
                    # unreachable
                denom = f + self.k1 * (1 - self.b + self.b * len(tokens) / self.avgdl)
                score += self._idf(qt) * f * (self.k1 + 1) / denom
            scores.append(score)
        ranked = sorted(zip(self.chunks, scores, strict=True), key=lambda pair: -pair[1])
        return [Scored(chunk=c, score=s) for c, s in ranked[:top_k] if s > 0]

    def chunk_by_id(self, chunk_id: str) -> DocumentChunk | None:  # type: ignore[valid-type]
        for chunk in self.chunks:
            if chunk.id == chunk_id if hasattr(chunk, "id") else chunk.chunk_id == chunk_id:
                return chunk
        return None
