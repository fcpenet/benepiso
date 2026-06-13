"""Orchestrate discovery: enumerate → fetch → parse → score → rank → report.

Fetched candidate texts are cached under ``discovery/cache/`` (git-ignored) so
re-runs and score-threshold sweeps don't re-hit the network. Laws already in the
benefits corpus are scored too but flagged ``in_corpus`` so reviewers can focus
on the genuinely new ones.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ingest.fetcher import Fetcher, FetchError
from ingest.parser import extract_text, looks_like_law
from ingest.registry import parse_ra_number
from benepisyoko.repository import load_benefits

from .scorer import extract_title, score_law
from .sources import discover_year

CACHE_DIR = Path(__file__).resolve().parent / "cache"
REPORT_PATH = Path(__file__).resolve().parent / "candidates.json"


@dataclass
class Candidate:
    law: str
    number: int
    year: int
    url: str
    title: str
    score: float
    in_corpus: bool
    signals: list[str] = field(default_factory=list)
    beneficiaries: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    snippet: str = ""


def _corpus_ra_numbers() -> set[int]:
    nums = set()
    for b in load_benefits():
        n = parse_ra_number(b.legal_basis.law)
        if n is not None:
            nums.add(n)
    return nums


def _cached_text(number: int, year: int, url: str, fetcher: Fetcher) -> str | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"RA-{number}-{year}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    try:
        text = extract_text(fetcher.get(url))
    except FetchError:
        return None
    except Exception:
        return None
    if not looks_like_law(text):
        return None
    path.write_text(text, encoding="utf-8")
    return text


def _write_report(candidates: list[Candidate]) -> None:
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
    REPORT_PATH.write_text(
        json.dumps([asdict(c) for c in ranked], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def discover(
    years: list[int],
    min_score: float = 4.0,
    limit_per_year: int | None = None,
    delay: float = 2.0,
    include_corpus: bool = False,
) -> list[Candidate]:
    corpus = _corpus_ra_numbers()
    candidates: list[Candidate] = []

    with Fetcher(delay=delay) as fetcher:
        for year in years:
            targets = discover_year(year, fetcher)
            if limit_per_year:
                targets = targets[:limit_per_year]
            print(f"[{year}] scanning {len(targets)} RAs…", flush=True)
            for number, yr, url in targets:
                in_corpus = number in corpus
                if in_corpus and not include_corpus:
                    continue
                text = _cached_text(number, yr, url, fetcher)
                if text is None:
                    continue
                title = extract_title(text)
                result = score_law(title, text)
                if result.score < min_score:
                    continue
                candidates.append(
                    Candidate(
                        law=f"RA {number}",
                        number=number,
                        year=yr,
                        url=url,
                        title=title,
                        score=result.score,
                        in_corpus=in_corpus,
                        signals=result.signals,
                        beneficiaries=result.beneficiaries,
                        negatives=result.negatives,
                        snippet=result.snippet,
                    )
                )
            # Checkpoint after every year so a long, interruptible run keeps its
            # progress (the per-law cache makes any resume cheap).
            _write_report(candidates)
            new = sum(1 for c in candidates if not c.in_corpus)
            print(f"[{year}] done. candidates so far: {len(candidates)} ({new} new)", flush=True)

    _write_report(candidates)
    return candidates
