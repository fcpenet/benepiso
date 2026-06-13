"""Law-text ingestion pipeline.

Fetches full statute text for the Republic Acts referenced by the benefits
corpus (and any extra seeds) from LawPhil, then stores the cleaned text plus a
manifest so corpus entries can be grounded in — and verified against — the
actual law rather than recall.
"""
