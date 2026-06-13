"""Offline tests for the RAG layer (no API key, no network)."""

import os

from benepisyoko.rag.chunker import load_chunks
from benepisyoko.rag.generator import generate_answer
from benepisyoko.rag.retriever import search


def test_chunks_load_from_ingested_laws():
    chunks = load_chunks()
    assert len(chunks) > 100  # 30 laws split into many sections
    # Every chunk carries citable metadata.
    assert all(c.law and c.title and c.year and c.text for c in chunks)
    # Sections were actually detected (not one giant preamble per law).
    assert any(c.section.lower().startswith("sec") for c in chunks)


def test_retriever_finds_maternity_leave():
    hits = search("paid maternity leave for working mothers", top_k=5)
    assert hits
    laws = {chunk.law for chunk, _ in hits}
    assert "RA 11210" in laws  # 105-Day Expanded Maternity Leave Law
    # Scores are sorted descending.
    scores = [score for _, score in hits]
    assert scores == sorted(scores, reverse=True)


def test_retriever_finds_solo_parent():
    hits = search("benefits and discounts for solo parents", top_k=5)
    laws = {chunk.law for chunk, _ in hits}
    assert "RA 11861" in laws


def test_retriever_respects_top_k():
    assert len(search("senior citizen discount", top_k=3)) <= 3


def test_empty_query_returns_nothing():
    assert search("", top_k=5) == []


def test_generator_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = generate_answer(
        "What is maternity leave?",
        [{"law": "RA 11210", "year": 2019, "section": "Sec. 3", "text": "..."}],
    )
    assert result is None


def test_generator_returns_none_with_no_sources(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert generate_answer("anything", []) is None
