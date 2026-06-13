"""Split the ingested statute texts into section-level passages.

Each `.txt` produced by the ingestion pipeline is broken at ``Section N`` /
``Sec. N`` headings; text before the first heading becomes a "Preamble" chunk.
Long sections are further split into overlapping windows so no single passage is
unwieldy. Each chunk carries the law's metadata (from the manifest) so retrieval
results can cite RA, title, year, and source URL.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LAWS_DIR = Path(__file__).resolve().parents[1] / "data" / "laws"
MANIFEST_PATH = LAWS_DIR / "manifest.json"

# Start-of-line "Section 1.", "Sec. 1", "SECTION 12-A.", etc.
_HEADING = re.compile(r"^\s*(SEC(?:TION|\.)?\s+\d+[A-Za-z\-]*\.?)", re.IGNORECASE)

_MAX_CHARS = 1800
_OVERLAP = 200


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    law: str
    title: str
    year: int
    source_url: str | None
    section: str
    text: str


def _split_long(text: str) -> list[str]:
    """Window an over-long section into overlapping pieces on whitespace."""
    if len(text) <= _MAX_CHARS:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = start + _MAX_CHARS
        if end < len(text):
            # back off to the last whitespace so we don't cut mid-word
            ws = text.rfind(" ", start, end)
            if ws > start:
                end = ws
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - _OVERLAP, start + 1)
    return [p for p in pieces if p]


def _sections(text: str) -> list[tuple[str, str]]:
    """Yield (heading, body) pairs from a statute's text."""
    sections: list[tuple[str, list[str]]] = [("Preamble", [])]
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            sections.append((m.group(1).strip().rstrip("."), [line]))
        else:
            sections[-1][1].append(line)
    out: list[tuple[str, str]] = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if body:
            out.append((heading, body))
    return out


def _chunks_for_law(entry: dict) -> list[Chunk]:
    text_file = entry.get("text_file")
    if not text_file:
        return []
    path = LAWS_DIR / text_file
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")

    chunks: list[Chunk] = []
    for section, body in _sections(raw):
        for i, piece in enumerate(_split_long(body)):
            chunks.append(
                Chunk(
                    chunk_id=f"{entry['slug']}#{len(chunks)}",
                    law=entry["law"],
                    title=entry.get("title") or entry["law"],
                    year=int(entry["year"]),
                    source_url=entry.get("url"),
                    section=section if i == 0 else f"{section} (cont.)",
                    text=piece,
                )
            )
    return chunks


@lru_cache(maxsize=1)
def load_chunks() -> list[Chunk]:
    if not MANIFEST_PATH.exists():
        return []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    chunks: list[Chunk] = []
    for entry in manifest.values():
        if entry.get("status") in ("ok", "suspect"):
            chunks.extend(_chunks_for_law(entry))
    return chunks
