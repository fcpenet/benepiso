"""Benefit-discovery pipeline.

Where `ingest/` *grounds* laws the corpus already cites, `discovery/` *finds new
ones*. It enumerates Republic Acts broadly from LawPhil's year indexes, fetches
and parses each (reusing `ingest.fetcher` / `ingest.parser`), and scores the text
for benefit-granting language. The output is a ranked list of candidate laws for
a human to review and, where appropriate, encode into the benefits corpus —
flagging which candidates are already covered.

This is a research/triage tool, never run in the serverless app.
"""
