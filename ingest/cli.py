"""Command-line entrypoint for the ingestion pipeline.

Examples:
    python -m ingest.cli --list                # show targets, fetch nothing
    python -m ingest.cli --all                 # ingest every corpus RA (+ extras)
    python -m ingest.cli --all --limit 3       # just the first 3 (good first run)
    python -m ingest.cli --ra 11916 --year 2022
    python -m ingest.cli --all --force         # re-fetch even if already stored
    python -m ingest.cli --status              # summarise the manifest
    python -m ingest.cli --link                # corpus RA -> ingested-text coverage
"""

from __future__ import annotations

import argparse
import sys

from benepisyoko.repository import load_benefits

from .fetcher import Fetcher
from .pipeline import LAWS_DIR, load_manifest
from .pipeline import ingest as run_ingest
from .registry import (
    LawTarget,
    all_targets,
    parse_ra_number,
    targets_from_corpus,
)


def _select_targets(args: argparse.Namespace) -> list[LawTarget]:
    if args.ra:
        if not args.year:
            sys.exit("--ra requires --year")
        return [LawTarget(law=f"RA {args.ra}", number=args.ra, year=args.year)]
    targets = all_targets(include_extra=not args.no_extra)
    if args.limit:
        targets = targets[: args.limit]
    return targets


def _cmd_list(args: argparse.Namespace) -> None:
    targets = _select_targets(args)
    print(f"{len(targets)} target(s):\n")
    for t in targets:
        print(f"  {t.slug:14}  {t.law:10}  {t.resolved_url()}")


def _cmd_status(_: argparse.Namespace) -> None:
    manifest = load_manifest()
    if not manifest:
        print("No manifest yet — run an ingest first.")
        return
    by_status: dict[str, int] = {}
    for entry in manifest.values():
        by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
    print(f"Manifest: {len(manifest)} law(s) in {LAWS_DIR}\n")
    for status, count in sorted(by_status.items()):
        print(f"  {status:9} {count}")
    print()
    for slug, e in sorted(manifest.items()):
        size = f"{e['char_count']:>7,}c" if e.get("char_count") else " " * 8
        note = f"  ! {e['error']}" if e.get("error") else ""
        print(f"  {slug:14} {e['status']:9} {size}{note}")


def _cmd_link(_: argparse.Namespace) -> None:
    """Show which corpus citations are backed by ingested law text."""
    manifest = load_manifest()
    ingested_ok = {
        slug for slug, e in manifest.items() if e.get("status") in ("ok", "suspect")
    }
    print("Corpus citation -> ingested law text:\n")
    missing = 0
    for benefit in load_benefits():
        lb = benefit.legal_basis
        number = parse_ra_number(lb.law)
        slug = f"RA-{number}-{lb.year}" if number else None
        have = slug in ingested_ok if slug else False
        mark = "✓" if have else ("—" if slug else "n/a (non-RA)")
        if slug and not have:
            missing += 1
        print(f"  {mark:4} {benefit.id:38} {lb.law} ({lb.year})")
    total = len(targets_from_corpus())
    print(f"\n{total - missing}/{total} distinct corpus RAs have ingested text.")


def _cmd_ingest(args: argparse.Namespace) -> None:
    targets = _select_targets(args)
    print(f"Ingesting {len(targets)} law(s) (delay={args.delay}s, force={args.force})…\n")
    with Fetcher(delay=args.delay) as fetcher:
        records = run_ingest(targets, fetcher=fetcher, force=args.force)
    for r in records:
        size = f"{r.char_count:,}c" if r.char_count else ""
        note = f"  ! {r.error}" if r.error else ""
        print(f"  [{r.status:8}] {r.slug:14} {size}{note}")
    ok = sum(1 for r in records if r.status in ("ok", "skipped", "suspect"))
    print(f"\nDone: {ok}/{len(records)} available. Texts in {LAWS_DIR}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingest", description="Ingest PH statute text from LawPhil.")
    p.add_argument("--all", action="store_true", help="Ingest all corpus targets (default action).")
    p.add_argument("--ra", type=int, help="Ingest a single RA number.")
    p.add_argument("--year", type=int, help="Year for --ra.")
    p.add_argument("--limit", type=int, help="Cap the number of targets.")
    p.add_argument("--delay", type=float, default=2.0, help="Seconds between requests (default 2.0).")
    p.add_argument("--force", action="store_true", help="Re-fetch even if already stored.")
    p.add_argument("--no-extra", action="store_true", help="Exclude EXTRA_SEEDS, corpus only.")
    p.add_argument("--list", action="store_true", help="List targets and exit.")
    p.add_argument("--status", action="store_true", help="Summarise the manifest and exit.")
    p.add_argument("--link", action="store_true", help="Show corpus->ingested coverage and exit.")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.list:
        _cmd_list(args)
    elif args.status:
        _cmd_status(args)
    elif args.link:
        _cmd_link(args)
    else:
        _cmd_ingest(args)


if __name__ == "__main__":
    main()
