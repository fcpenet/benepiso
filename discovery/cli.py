"""Command-line entry for the discovery pipeline.

Examples:
    # Scan all of 2019, report laws scoring >= 6 that aren't already in the corpus
    python -m discovery.cli --years 2019 --min-score 6

    # A quick bounded trial: first 10 RAs of two years
    python -m discovery.cli --years 2018,2019 --limit 10 --min-score 4

    # Include laws already in the corpus (to sanity-check the scorer)
    python -m discovery.cli --years 2022 --include-corpus
"""

from __future__ import annotations

import argparse

from .pipeline import REPORT_PATH, discover


def _parse_years(raw: str) -> list[int]:
    years: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            years.extend(range(int(lo), int(hi) + 1))
        elif part:
            years.append(int(part))
    return years


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="discovery", description="Find candidate benefit-granting RAs on LawPhil."
    )
    p.add_argument("--years", required=True, help="e.g. '2019' or '2018,2019' or '2015-2019'.")
    p.add_argument("--min-score", type=float, default=4.0, help="Report cutoff (default 4.0).")
    p.add_argument("--limit", type=int, help="Cap RAs scanned per year (for trials).")
    p.add_argument("--delay", type=float, default=2.0, help="Seconds between requests.")
    p.add_argument("--include-corpus", action="store_true", help="Also report laws already in the corpus.")
    p.add_argument("--top", type=int, default=25, help="How many to print (all are written to the report).")
    args = p.parse_args(argv)

    years = _parse_years(args.years)
    print(f"Scanning {years} (min_score={args.min_score}, delay={args.delay}s)…\n")
    candidates = discover(
        years=years,
        min_score=args.min_score,
        limit_per_year=args.limit,
        delay=args.delay,
        include_corpus=args.include_corpus,
    )

    new = [c for c in candidates if not c.in_corpus]
    print(f"{len(candidates)} candidate(s) ≥ {args.min_score}  ({len(new)} not yet in corpus)\n")
    for c in candidates[: args.top]:
        tag = " [in corpus]" if c.in_corpus else ""
        print(f"  {c.score:5.1f}  {c.law} ({c.year}){tag}")
        print(f"         {c.title[:90]}")
        if c.beneficiaries:
            print(f"         for: {', '.join(c.beneficiaries)}")
        print(f"         signals: {', '.join(c.signals[:8])}")
        if c.snippet:
            print(f"         “{c.snippet[:140]}”")
        print()
    print(f"Full report ({len(candidates)}): {REPORT_PATH}")


if __name__ == "__main__":
    main()
