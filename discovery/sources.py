"""Enumerate Republic Acts from LawPhil's per-year index pages.

LawPhil lists each year's statutes on an index page; the entries link to the
individual ``ra_<num>_<year>.html`` documents. We fetch that index and harvest
every such link, which gives us (number, year, url) for the whole year without
having to guess RA numbers.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from ingest.fetcher import Fetcher

_INDEX_CANDIDATES = (
    "https://lawphil.net/statutes/repacts/ra{year}/ra{year}.html",
    "https://lawphil.net/statutes/repacts/ra{year}.html",
)

# Match links to individual RA documents, capturing href, number, year.
_DOC_LINK = re.compile(
    r'href\s*=\s*["\']([^"\']*ra_(\d+)_(\d+)\.html)["\']', re.IGNORECASE
)


def _index_urls(year: int) -> list[str]:
    return [u.format(year=year) for u in _INDEX_CANDIDATES]


def discover_year(year: int, fetcher: Fetcher) -> list[tuple[int, int, str]]:
    """Return distinct (ra_number, year, absolute_url) for the given year."""
    html = ""
    base = ""
    for url in _index_urls(year):
        try:
            html = fetcher.get(url).decode("utf-8", errors="ignore")
            base = url
            break
        except Exception:
            continue
    if not html:
        return []

    seen: dict[int, tuple[int, int, str]] = {}
    for href, num, yr in _DOC_LINK.findall(html):
        number = int(num)
        if number in seen:
            continue
        seen[number] = (number, int(yr), urljoin(base, href))
    return sorted(seen.values())
