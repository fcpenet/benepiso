"""Orchestrates fetch -> parse -> store for a set of LawTargets, maintaining a
manifest so runs are idempotent and the store is auditable."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .fetcher import Fetcher, FetchError
from .parser import extract_text, looks_like_law
from .registry import LawTarget

LAWS_DIR = Path(__file__).resolve().parents[1] / "benepisyoko" / "data" / "laws"
MANIFEST_PATH = LAWS_DIR / "manifest.json"


@dataclass
class IngestRecord:
    law: str
    title: Optional[str]
    year: int
    slug: str
    url: str
    status: str  # "ok" | "skipped" | "failed" | "suspect"
    fetched_at: Optional[str] = None
    char_count: Optional[int] = None
    sha256: Optional[str] = None
    text_file: Optional[str] = None
    error: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_manifest() -> dict[str, dict]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _write_manifest(manifest: dict[str, dict]) -> None:
    LAWS_DIR.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(manifest.items()))
    MANIFEST_PATH.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def ingest(
    targets: list[LawTarget],
    fetcher: Optional[Fetcher] = None,
    force: bool = False,
) -> list[IngestRecord]:
    """Fetch and store each target. Existing texts are skipped unless `force`."""
    LAWS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()

    owns_fetcher = fetcher is None
    fetcher = fetcher or Fetcher()
    records: list[IngestRecord] = []

    try:
        for target in targets:
            slug = target.slug
            text_path = LAWS_DIR / f"{slug}.txt"
            url = target.resolved_url()

            if text_path.exists() and not force:
                records.append(
                    IngestRecord(
                        law=target.law, title=target.title, year=target.year,
                        slug=slug, url=url, status="skipped",
                        text_file=text_path.name,
                        **_existing_stats(manifest.get(slug)),
                    )
                )
                continue

            rec = IngestRecord(
                law=target.law, title=target.title, year=target.year,
                slug=slug, url=url, status="failed",
            )
            try:
                html = fetcher.get(url)
                text = extract_text(html)
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                text_path.write_text(text, encoding="utf-8")
                rec.fetched_at = _now()
                rec.char_count = len(text)
                rec.sha256 = digest
                rec.text_file = text_path.name
                rec.status = "ok" if looks_like_law(text) else "suspect"
            except FetchError as exc:
                rec.error = str(exc)
            except Exception as exc:  # noqa: BLE001 - record any failure, keep going
                rec.error = f"{type(exc).__name__}: {exc}"

            records.append(rec)
            manifest[slug] = {
                k: v for k, v in asdict(rec).items() if v is not None
            }
            _write_manifest(manifest)  # checkpoint after every law
    finally:
        if owns_fetcher:
            fetcher.close()

    return records


def _existing_stats(entry: Optional[dict]) -> dict:
    if not entry:
        return {}
    return {
        k: entry.get(k)
        for k in ("fetched_at", "char_count", "sha256")
        if entry.get(k) is not None
    }
