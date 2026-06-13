"""Turn a LawPhil HTML page into clean, stored-ready statute text."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_BLANK_RUN = re.compile(r"\n{3,}")
# LawPhil scatters anti-scrape watermark tokens through the text — variants of
# "lawphil" with digits/Cyrillic look-alikes, e.g. "1aшphi1", "lawphi1".
_WATERMARK = re.compile(r"^\W*\d*\s*[a-zа-я]{0,3}phi[l1]\d*\W*$", re.IGNORECASE)


def extract_text(html: str | bytes) -> str:
    """Strip scripts/markup and return the page's readable text.

    LawPhil pages are plain, table-light HTML, so the body text (minus
    script/style/nav noise) is a faithful rendering of the statute. Passing the
    raw bytes lets BeautifulSoup detect the page's (often legacy) charset, which
    avoids mis-decoded dashes and other punctuation. We keep paragraph breaks,
    drop LawPhil's inline watermark tokens, and collapse excessive blank lines.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()

    body = soup.body or soup
    text = body.get_text("\n")

    lines = [line.strip() for line in text.splitlines()]
    lines = ["" if _WATERMARK.match(line) else line for line in lines]
    # Drop empty lines but preserve single blanks between paragraphs.
    cleaned: list[str] = []
    for line in lines:
        if line or (cleaned and cleaned[-1] != ""):
            cleaned.append(line)
    out = "\n".join(cleaned).strip()
    return _BLANK_RUN.sub("\n\n", out)


def looks_like_law(text: str) -> bool:
    """Heuristic sanity check that we actually fetched a statute page and not a
    'not found' / index page."""
    if len(text) < 400:
        return False
    lowered = text.lower()
    markers = ("republic act", "be it enacted", "section 1", "sec. 1")
    return any(m in lowered for m in markers)
