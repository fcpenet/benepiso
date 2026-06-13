"""Offline tests for the discovery scorer (no network)."""

from discovery.scorer import extract_title, score_law

_BENEFIT_LAW = """
Tenth Congress
AN ACT GRANTING ADDITIONAL BENEFITS AND PRIVILEGES TO SENIOR CITIZENS
Be it enacted...
Section 4. Privileges for the Senior Citizens. — The senior citizens shall be
entitled to the grant of twenty percent (20%) discount and exemption from the
value-added tax on the sale of goods and a monthly social pension for indigent
senior citizens.
"""

_STRUCTURAL_LAW = """
AN ACT RENAMING THE MARCELO FERNAN BRIDGE LOCATED IN CEBU
Be it enacted...
Section 1. The bridge shall be known as the Marcelo Fernan Bridge.
"""


def test_extract_title():
    assert extract_title(_BENEFIT_LAW).startswith("AN ACT GRANTING ADDITIONAL BENEFITS")


def test_benefit_law_scores_high():
    s = score_law(extract_title(_BENEFIT_LAW), _BENEFIT_LAW)
    assert s.score >= 6
    assert "senior citizens" in s.beneficiaries
    # picked up entitlement + discount + VAT + social pension signals
    assert any("entitled" in sig for sig in s.signals)
    assert s.snippet  # a representative sentence was lifted


def test_structural_law_scores_low():
    s = score_law(extract_title(_STRUCTURAL_LAW), _STRUCTURAL_LAW)
    assert s.score < 4
    assert "renamer/declaration" in s.negatives


def test_empty_text_scores_zero_or_less():
    assert score_law("AN ACT", "").score <= 0
