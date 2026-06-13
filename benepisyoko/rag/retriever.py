"""A small, dependency-free TF-IDF retriever over the statute chunks.

No numpy, no embeddings service, no API key — it builds an in-memory index from
the bundled law texts at first use and answers top-k cosine-similarity queries.
This keeps the serverless function lean and means retrieval always works; the
optional Claude layer (see `generator.py`) sits on top of these results.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from .chunker import Chunk, load_chunks

_TOKEN = re.compile(r"[a-z0-9]+")

# Tiny stopword set — enough to de-weight filler without a linguistics library.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "by", "with",
    "as", "at", "is", "are", "be", "been", "this", "that", "these", "those",
    "shall", "such", "any", "all", "from", "which", "who", "whom",
    "it", "its", "their", "his", "her", "they", "he", "she", "not", "no",
}


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in _STOP]


class _Index:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.idf: dict[str, float] = {}
        self.vectors: list[dict[str, float]] = []
        self._build()

    def _build(self) -> None:
        n = len(self.chunks)
        df: Counter[str] = Counter()
        tokenized: list[Counter[str]] = []
        for chunk in self.chunks:
            counts = Counter(_tokenize(f"{chunk.section}\n{chunk.text}"))
            tokenized.append(counts)
            df.update(counts.keys())
        # Smoothed idf so a term in every doc still contributes a little.
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
        for counts in tokenized:
            self.vectors.append(self._weight(counts))

    def _weight(self, counts: Counter[str]) -> dict[str, float]:
        vec = {t: (1 + math.log(c)) * self.idf.get(t, 0.0) for t, c in counts.items()}
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        return {t: w / norm for t, w in vec.items()}

    def search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        q = self._weight(Counter(_tokenize(query)))
        if not q:
            return []
        scored: list[tuple[Chunk, float]] = []
        for chunk, vec in zip(self.chunks, self.vectors):
            # Iterate the smaller vector for the sparse dot product.
            small, big = (q, vec) if len(q) <= len(vec) else (vec, q)
            score = sum(w * big.get(t, 0.0) for t, w in small.items())
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


@lru_cache(maxsize=1)
def _index() -> _Index:
    return _Index(load_chunks())


def search(query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
    return _index().search(query, top_k)
