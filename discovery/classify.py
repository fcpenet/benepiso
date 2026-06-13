"""LLM triage on top of discovery — separate real individual-benefit laws from
the codes / tax / structural statutes that keyword scoring can't tell apart.

For each candidate it asks Claude (`claude-opus-4-8`) a tightly-scoped question
against the law text and returns a structured judgement: does this grant a
benefit to an *individual natural person*, what is it, who's it for, and how
confident. Env-gated on ANTHROPIC_API_KEY; without a key (or the SDK) it returns
None and the caller falls back to the keyword ranking.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

MODEL = "claude-opus-4-8"
# Cap how much statute text we send per call — operative benefit provisions are
# near the front, and this keeps a 300-candidate sweep affordable.
_MAX_CHARS = 14000

_SYSTEM = (
    "You triage Philippine Republic Acts to find ones that grant a concrete "
    "benefit to an INDIVIDUAL natural person (a citizen, worker, patient, "
    "student, senior, PWD, etc.) that they could claim.\n"
    "Judge ONLY from the provided text. Decide:\n"
    "- grants_individual_benefit: true only if a natural person gains a "
    "claimable benefit (discount, cash, pension, leave, exemption, free "
    "service, scholarship, priority, reserved slot…). False for laws that only "
    "create agencies/LGUs, set corporate/tax/tariff rules, appropriate funds, "
    "or grant benefits solely to companies/cooperatives/government bodies.\n"
    "- benefit_summary: one sentence on what the individual gets (or why not).\n"
    "- beneficiaries: the natural-person groups it targets.\n"
    "- benefit_type: one of discount, cash, pension, leave, exemption, "
    "service, scholarship, employment, housing, other, none.\n"
    "- confidence: 0-1.\n"
    "- rationale: brief, grounded in the text."
)


class Classification(BaseModel):
    grants_individual_benefit: bool
    benefit_summary: str
    beneficiaries: list[str] = Field(default_factory=list)
    benefit_type: str
    confidence: float
    rationale: str


def classify_law(title: str, text: str) -> Classification | None:
    """Classify one law, or None if the LLM is unavailable/unconfigured."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None

    excerpt = text[:_MAX_CHARS]
    try:
        client = anthropic.Anthropic()
        response = client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Title: {title}\n\nText (truncated):\n{excerpt}",
                }
            ],
            output_format=Classification,
        )
    except Exception:
        return None

    return response.parsed_output


def main(argv: list[str] | None = None) -> None:
    """CLI: triage the discovery candidate report with the LLM.

    Examples:
        python -m discovery.classify --min-score 8 --limit 50
        python -m discovery.classify --only-benefits
    """
    import argparse
    import json
    from pathlib import Path

    from .pipeline import CACHE_DIR, REPORT_PATH

    p = argparse.ArgumentParser(prog="discovery.classify", description=__doc__)
    p.add_argument("--in", dest="infile", default=str(REPORT_PATH),
                   help="Candidate report to classify (default: candidates.json).")
    p.add_argument("--out", default=str(Path(REPORT_PATH).with_name("classified.json")))
    p.add_argument("--min-score", type=float, default=0.0, help="Only classify candidates ≥ this keyword score.")
    p.add_argument("--limit", type=int, help="Cap how many candidates to classify.")
    p.add_argument("--only-benefits", action="store_true", help="Write only those judged to grant an individual benefit.")
    p.add_argument("--top", type=int, default=25)
    args = p.parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set — classification needs it. "
            "Set it and re-run (the keyword report in candidates.json still stands without it)."
        )

    candidates = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    candidates = [c for c in candidates if c["score"] >= args.min_score]
    if args.limit:
        candidates = candidates[: args.limit]

    print(f"Classifying {len(candidates)} candidate(s) with {MODEL}…\n", flush=True)
    results = []
    for c in candidates:
        path = CACHE_DIR / f"RA-{c['number']}-{c['year']}.txt"
        if not path.exists():
            continue
        verdict = classify_law(c["title"], path.read_text(encoding="utf-8"))
        if verdict is None:
            continue
        record = {**c, "classification": verdict.model_dump()}
        if args.only_benefits and not verdict.grants_individual_benefit:
            continue
        results.append(record)

    # Real benefits first, then by model confidence, then keyword score.
    results.sort(
        key=lambda r: (
            r["classification"]["grants_individual_benefit"],
            r["classification"]["confidence"],
            r["score"],
        ),
        reverse=True,
    )
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    benefits = [r for r in results if r["classification"]["grants_individual_benefit"]]
    print(f"{len(benefits)} judged to grant an individual benefit (of {len(results)} classified)\n")
    for r in benefits[: args.top]:
        cl = r["classification"]
        print(f"  {cl['confidence']:.2f}  {r['law']} ({r['year']})  [{cl['benefit_type']}]")
        print(f"        {r['title'][:80]}")
        print(f"        {cl['benefit_summary'][:150]}")
        print()
    print(f"Full classified report: {args.out}")


if __name__ == "__main__":
    main()
