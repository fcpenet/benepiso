"""Heuristic scoring of a statute's text for *individual benefit-granting* language.

The goal is recall-oriented triage: flag laws that plausibly confer a claimable
benefit on an individual, so a human can review the high-scoring ones. It is not
a classifier and makes no legal judgement — it counts weighted signal phrases,
notes who the likely beneficiaries are, lifts a representative snippet, and
lightly penalises titles that are obviously structural (renaming a road,
creating an agency) rather than benefit-granting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# (regex, weight, label). Strong = explicit entitlement/grant language.
_STRONG = [
    (r"shall be entitled to", 3, "shall be entitled to"),
    (r"shall be granted", 3, "shall be granted"),
    (r"shall enjoy", 2, "shall enjoy"),
    (r"shall be exempt(?:ed)? from", 3, "exempt from"),
    (r"\b\d{1,3}\s?% ?(?:discount|off)", 3, "percent discount"),
    (r"\bdiscount\b", 2, "discount"),
    (r"\bvat[- ]exempt", 3, "VAT exemption"),
    (r"free of charge", 2, "free of charge"),
    (r"social pension", 3, "social pension"),
    (r"cash (?:assistance|subsidy|grant|gift|incentive)", 3, "cash assistance"),
    (r"monthly (?:stipend|pension|allowance)", 3, "monthly stipend/pension"),
    (r"scholarship", 2, "scholarship"),
    (r"leave (?:of|with|benefit|credits)", 2, "leave benefit"),
]

_MEDIUM = [
    (r"\bsubsid(?:y|ies|ized)\b", 2, "subsidy"),
    (r"\ballowance\b", 2, "allowance"),
    (r"\bincentives?\b", 1, "incentive"),
    (r"\bprivileges?\b", 2, "privilege"),
    (r"\bbenefits?\b", 1, "benefits"),
    (r"\bassistance\b", 1, "assistance"),
    (r"\bwaiv(?:e|ed|er)\b", 2, "fee waiver"),
    (r"\bexemption\b", 1, "exemption"),
    (r"\bpension\b", 2, "pension"),
    (r"\binsurance\b", 1, "insurance"),
    (r"\bcredit assistance\b", 2, "credit assistance"),
]

# Beneficiary-type cues — who the law seems aimed at. Capped contribution.
_BENEFICIARY = [
    (r"senior citizens?", "senior citizens"),
    (r"persons? with disabilit", "PWD"),
    (r"solo parents?", "solo parents"),
    (r"\bfarmers?\b|fisherfolk|fisher(?:man|men)", "farmers/fisherfolk"),
    (r"\bworkers?\b|\bemployees?\b", "workers"),
    (r"\bstudents?\b|learners?", "students"),
    (r"\bwomen\b|\bmothers?\b|\bpregnant\b", "women/mothers"),
    (r"\bchildren\b|\bminors?\b|\binfants?\b", "children"),
    (r"\bindigent\b|\bpoor\b|marginalized", "indigent"),
    (r"overseas filipino|migrant workers?|\bofws?\b", "OFWs"),
    (r"\bteachers?\b", "teachers"),
    (r"health workers?|\bnurses?\b|midwi(?:fe|ves)", "health workers"),
    (r"veterans?", "veterans"),
    (r"indigenous (?:peoples?|cultural)", "indigenous peoples"),
]

# Titles that are structural, not individual-benefit laws. When matched these
# strongly dampen the score (boilerplate like board "reimbursements" or
# "scholarship" otherwise inflates charters and reorg laws). Patterns are
# written to avoid catching genuine benefit laws (e.g. Malasakit "Establishing
# … Centers", which is not an educational charter).
_NEGATIVE_TITLE = [
    (r"\brenaming\b|\bdeclaring\b", "renamer/declaration"),
    (r"\bconverting\b", "conversion/charter"),
    (r"(?:establishing|integrating|separating).{0,70}"
     r"(?:state university|state college|polytechnic|community college|"
     r"science high school)", "educational charter"),
    (r"creating the .{0,60}(?:authority|commission|office|council|institute|"
     r"bureau|administration)\b", "agency-creation"),
    (r"general appropriations|appropriating funds for the operation", "appropriations"),
    (r"\bcharter of\b", "charter"),
    (r"increasing the (?:bed|student|enrollment) capacity", "capacity"),
    (r"\bmerging\b|\babolishing\b", "reorg"),
]

_BENEFICIARY_CAP = 4  # don't let beneficiary cues dominate the score


def _compile(specs):
    return [(re.compile(p, re.IGNORECASE), w, label) for p, w, label in specs]


_STRONG_C = _compile(_STRONG)
_MEDIUM_C = _compile(_MEDIUM)
_BENEFICIARY_C = [(re.compile(p, re.IGNORECASE), label) for p, label in _BENEFICIARY]
_NEGATIVE_C = [(re.compile(p, re.IGNORECASE), label) for p, label in _NEGATIVE_TITLE]

_TITLE = re.compile(r"^\s*AN ACT\b.*", re.IGNORECASE | re.MULTILINE)


@dataclass
class Score:
    score: float
    signals: list[str] = field(default_factory=list)
    beneficiaries: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    snippet: str = ""


def extract_title(text: str) -> str:
    m = _TITLE.search(text)
    if m:
        return re.sub(r"\s+", " ", m.group(0)).strip()[:300]
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return first[:300]


def _snippet(text: str) -> str:
    """A representative sentence around the first strong signal."""
    text = re.sub(r"\s+", " ", text)
    for pattern, _, _ in _STRONG_C:
        m = pattern.search(text)
        if m:
            start = max(text.rfind(".", 0, m.start()) + 1, m.start() - 160)
            end = text.find(".", m.end())
            end = end + 1 if end != -1 else m.end() + 160
            return re.sub(r"\s+", " ", text[start:end]).strip()[:320]
    return ""


def score_law(title: str, text: str) -> Score:
    # Collapse wrapped whitespace so multi-word phrases match across line breaks.
    hay = re.sub(r"\s+", " ", f"{title}\n{text}")
    score = 0.0
    signals: list[str] = []

    for pattern, weight, label in _STRONG_C + _MEDIUM_C:
        if pattern.search(hay):
            score += weight
            signals.append(label)

    beneficiaries = [label for pattern, label in _BENEFICIARY_C if pattern.search(hay)]
    score += min(len(beneficiaries), _BENEFICIARY_CAP)

    # A structural title (charter, reorg, renamer) strongly dampens the score —
    # such laws carry benefit-like boilerplate without granting an individual
    # benefit. Proportional so a genuinely benefit-dense text isn't fully zeroed.
    negatives = [label for pattern, label in _NEGATIVE_C if pattern.search(title)]
    if negatives:
        score *= 0.15

    return Score(
        score=round(score, 1),
        signals=signals,
        beneficiaries=beneficiaries,
        negatives=negatives,
        snippet=_snippet(text),
    )
