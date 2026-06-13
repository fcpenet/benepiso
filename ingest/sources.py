"""Source URL builders.

LawPhil exposes Republic Acts at a stable, year-partitioned path:

    https://lawphil.net/statutes/repacts/ra{YEAR}/ra_{NUMBER}_{YEAR}.html

e.g. RA 11916 (2022) -> .../repacts/ra2022/ra_11916_2022.html

The {YEAR} is the year LawPhil files the law under, which is its year of
enactment/approval — the same `year` we store in each benefit's legal basis.
"""

from __future__ import annotations

LAWPHIL_BASE = "https://lawphil.net/statutes/repacts"


def lawphil_url(number: int, year: int) -> str:
    return f"{LAWPHIL_BASE}/ra{year}/ra_{number}_{year}.html"
