"""Offline tests for the ingestion pipeline (no network)."""

from ingest.parser import extract_text, looks_like_law
from ingest.registry import (
    LawTarget,
    all_targets,
    parse_ra_number,
    targets_from_corpus,
)
from ingest.sources import lawphil_url


def test_lawphil_url_pattern():
    assert lawphil_url(11916, 2022) == (
        "https://lawphil.net/statutes/repacts/ra2022/ra_11916_2022.html"
    )


def test_parse_ra_number_variants():
    assert parse_ra_number("RA 11916") == 11916
    assert parse_ra_number("R.A. 9710") == 9710
    assert parse_ra_number("RA0010801") == 10801
    assert parse_ra_number("PD 851") is None
    assert parse_ra_number("") is None


def test_target_slug_and_url():
    t = LawTarget(law="RA 9710", number=9710, year=2009)
    assert t.slug == "RA-9710-2009"
    assert t.resolved_url().endswith("ra2009/ra_9710_2009.html")


def test_explicit_url_override():
    t = LawTarget(law="RA 1", number=1, year=2000, url="https://example.test/x")
    assert t.resolved_url() == "https://example.test/x"


def test_targets_derived_from_corpus():
    targets = targets_from_corpus()
    numbers = {t.number for t in targets}
    # A few RAs we know the corpus cites.
    assert {11916, 9710, 11199, 10801}.issubset(numbers)
    # No duplicates by slug.
    slugs = [t.slug for t in targets]
    assert len(slugs) == len(set(slugs))


def test_all_targets_includes_extra_seeds():
    with_extra = {t.number for t in all_targets(include_extra=True)}
    without = {t.number for t in all_targets(include_extra=False)}
    assert 8972 in with_extra  # RA 8972 is an extra seed
    assert 8972 not in without


def test_extract_text_strips_markup():
    html = """
    <html><head><title>x</title><style>.a{}</style></head>
    <body><script>var z=1;</script>
    <h1>Republic Act No. 9999</h1>
    <p>Be it enacted by the Senate.</p>
    <p>Section 1. Title.</p></body></html>
    """
    text = extract_text(html)
    assert "var z" not in text
    assert ".a{}" not in text
    assert "Republic Act No. 9999" in text
    assert "Section 1. Title." in text


def test_looks_like_law_heuristic():
    real = "Republic Act No. 9999 " + ("Be it enacted. Section 1. " * 30)
    assert looks_like_law(real)
    assert not looks_like_law("404 Not Found")
    assert not looks_like_law("")
