"""Retrieval-augmented question answering over the ingested statute texts.

`chunker`   — splits each stored law into section-level passages with metadata.
`retriever` — a dependency-free TF-IDF index over those passages (always works,
              no API key, runs in the serverless function).
`generator` — optional synthesis of a cited answer via Claude, gated behind
              ANTHROPIC_API_KEY. Without a key the API returns the retrieved
              passages directly (extractive mode).
"""
