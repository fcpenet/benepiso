"""The list of laws to ingest.

The primary registry is *derived from the benefits corpus itself* — every RA a
benefit cites becomes an ingestion target — so the law store stays in sync with
the benefits we actually model. Extra seeds (benefit-granting laws not yet in
the corpus) can be added in EXTRA_SEEDS to grow coverage ahead of the corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from benepisyoko.repository import load_benefits

from .sources import lawphil_url

_RA_RE = re.compile(r"R\.?\s*A\.?\s*0*(\d{3,5})", re.IGNORECASE)


def parse_ra_number(law: str) -> Optional[int]:
    """Extract the numeric part of an 'RA NNNNN' string. Returns None for
    non-RA citations (e.g. 'PD 851'), which LawPhil files under a different path."""
    m = _RA_RE.search(law or "")
    return int(m.group(1)) if m else None


@dataclass(frozen=True)
class LawTarget:
    law: str
    number: int
    year: int
    title: Optional[str] = None
    url: Optional[str] = None  # explicit override; otherwise built from LawPhil

    @property
    def slug(self) -> str:
        return f"RA-{self.number}-{self.year}"

    def resolved_url(self) -> str:
        return self.url or lawphil_url(self.number, self.year)


# Benefit-granting laws to ingest even if not (yet) in the corpus. Add as the
# corpus grows or to pre-fetch candidates for new benefits.
EXTRA_SEEDS: list[LawTarget] = [
    LawTarget("RA 8972", 8972, 2000, "Solo Parents' Welfare Act of 2000"),
    LawTarget("RA 7432", 7432, 1992, "Senior Citizens Act of 1992"),
    LawTarget("RA 10868", 10868, 2016, "Centenarians Act of 2016"),
    LawTarget("RA 9442", 9442, 2007, "Magna Carta for Disabled Persons (amendment)"),
    LawTarget("RA 12078", 12078, 2024, "Act extending RCEF (amends RA 11203)"),
]


def targets_from_corpus() -> list[LawTarget]:
    """One LawTarget per distinct (RA number, year) cited in the corpus."""
    seen: dict[tuple[int, int], LawTarget] = {}
    for benefit in load_benefits():
        lb = benefit.legal_basis
        number = parse_ra_number(lb.law)
        if number is None:
            continue  # skip PDs / non-RA citations
        key = (number, lb.year)
        seen.setdefault(
            key, LawTarget(law=lb.law, number=number, year=lb.year, title=lb.title)
        )
    return list(seen.values())


def all_targets(include_extra: bool = True) -> list[LawTarget]:
    targets = {t.slug: t for t in targets_from_corpus()}
    if include_extra:
        for t in EXTRA_SEEDS:
            targets.setdefault(t.slug, t)
    return sorted(targets.values(), key=lambda t: (t.year, t.number))
