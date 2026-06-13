"""Tests for the eligibility engine and the corpus integrity."""

from benepisyoko.engine import match_all, match_benefit
from benepisyoko.models import Criteria, EligibilityRule, Benefit, LegalBasis
from benepisyoko.repository import load_benefits


def _ids(results):
    return {r.benefit.id for r in results}


def make_benefit(eid="x", **rule_kwargs) -> Benefit:
    return Benefit(
        id=eid,
        name="Test",
        category="test",
        description="d",
        benefit_value="v",
        legal_basis=LegalBasis(law="RA 1", title="t", year=2000),
        eligibility=EligibilityRule(**rule_kwargs),
    )


def test_corpus_loads_and_validates():
    benefits = load_benefits()
    assert len(benefits) >= 15
    # every benefit cites a law
    assert all(b.legal_basis.law for b in benefits)


def test_verified_entries_carry_provenance():
    """Entries checked against sources should record date + source URL."""
    verified = [b for b in load_benefits() if b.legal_basis.last_verified]
    assert verified, "expected some verified entries"
    for b in verified:
        assert b.legal_basis.source_url, f"{b.id} verified but has no source_url"
        # effective_date present for verified laws
        assert b.legal_basis.effective_date, f"{b.id} missing effective_date"


def test_amendment_tracking_on_social_pension():
    pension = next(b for b in load_benefits() if b.id == "senior-social-pension")
    amendments = pension.legal_basis.amendments
    assert any(a.law == "RA 11916" and a.effective_date == "2024-01" for a in amendments)


def test_ofw_sees_owwa_benefits():
    resp = match_all(load_benefits(), Criteria(employment_status="ofw"))
    assert "owwa-member-benefits" in _ids(resp.eligible)


def test_centenarian_gift_requires_age_80():
    resp = match_all(load_benefits(), Criteria(age=82))
    assert "octogenarian-centenarian-cash-gift" in _ids(resp.eligible)
    resp_young = match_all(load_benefits(), Criteria(age=50))
    gift_ids = _ids(resp_young.eligible) | _ids(resp_young.potential)
    assert "octogenarian-centenarian-cash-gift" not in gift_ids


def test_age_below_minimum_is_contradicted_and_dropped():
    senior = make_benefit("senior", min_age=60)
    resp = match_all([senior], Criteria(age=30))
    assert "senior" not in _ids(resp.eligible)
    assert "senior" not in _ids(resp.potential)  # contradicted -> dropped


def test_age_meets_minimum_is_eligible():
    senior = make_benefit("senior", min_age=60)
    resp = match_all([senior], Criteria(age=65))
    assert "senior" in _ids(resp.eligible)


def test_missing_age_is_potential_not_eligible():
    senior = make_benefit("senior", min_age=60)
    resp = match_all([senior], Criteria())  # age unknown
    assert "senior" in _ids(resp.potential)
    assert "senior" not in _ids(resp.eligible)


def test_gender_mismatch_dropped():
    women = make_benefit("women", gender="female")
    resp = match_all([women], Criteria(gender="male"))
    assert "women" not in _ids(resp.eligible) | _ids(resp.potential)


def test_income_ceiling():
    indigent = make_benefit("indigent", max_monthly_income=10000)
    assert "indigent" in _ids(match_all([indigent], Criteria(monthly_income=8000)).eligible)
    assert "indigent" not in _ids(
        match_all([indigent], Criteria(monthly_income=20000)).potential
    )


def test_required_flag_missing_is_potential():
    solo = make_benefit("solo", required_flags=["solo_parent"])
    resp = match_all([solo], Criteria())
    assert "solo" in _ids(resp.potential)
    resp2 = match_all([solo], Criteria(flags=["solo_parent"]))
    assert "solo" in _ids(resp2.eligible)


def test_any_flags():
    b = make_benefit("anyf", any_flags=["indigent", "has_children"])
    assert "anyf" in _ids(match_all([b], Criteria(flags=["has_children"])).eligible)


def test_no_conditions_is_universally_eligible():
    universal = make_benefit("uhc")  # empty rule
    assert "uhc" in _ids(match_all([universal], Criteria()).eligible)


def test_region_restriction():
    b = make_benefit("ncr", regions=["NCR"])
    assert "ncr" in _ids(match_all([b], Criteria(region="NCR")).eligible)
    assert "ncr" not in _ids(match_all([b], Criteria(region="Region I")).potential)


def test_match_result_reports_missing_for_potential():
    solo = make_benefit("solo", required_flags=["solo_parent"])
    result = match_benefit(solo, Criteria())
    assert result.missing  # should explain what to declare
    assert not result.eligible


def test_occupation_matches_sector_benefit():
    b = make_benefit("agri", occupations=["farmer", "fisherfolk"])
    assert "agri" in _ids(match_all([b], Criteria(occupation="farmer")).eligible)


def test_occupation_mismatch_is_contradicted_and_dropped():
    b = make_benefit("agri", occupations=["farmer"])
    resp = match_all([b], Criteria(occupation="teacher"))
    assert "agri" not in _ids(resp.eligible) | _ids(resp.potential)


def test_occupation_unknown_is_potential():
    b = make_benefit("agri", occupations=["farmer"])
    resp = match_all([b], Criteria())  # occupation not provided
    assert "agri" in _ids(resp.potential)


def test_farmer_query_surfaces_agriculture_laws():
    """'What laws help farmers?' — occupation alone should surface the sector."""
    resp = match_all(load_benefits(), Criteria(occupation="farmer"))
    eligible_ids = _ids(resp.eligible)
    assert {"free-irrigation-service", "rice-farmer-rcef-support",
            "sagip-saka-enterprise"}.issubset(eligible_ids)
    # Agrarian debt condonation also needs the ARB flag, so it's only potential.
    assert "agrarian-debt-condonation" in _ids(resp.potential)
    # Confirm it becomes eligible once the flag is declared.
    resp2 = match_all(
        load_benefits(),
        Criteria(occupation="farmer", flags=["agrarian_reform_beneficiary"]),
    )
    assert "agrarian-debt-condonation" in _ids(resp2.eligible)


def test_nurse_query_surfaces_health_worker_magna_carta():
    resp = match_all(
        load_benefits(),
        Criteria(occupation="health_worker", employment_status="employed"),
    )
    assert "public-health-worker-benefits" in _ids(resp.eligible)


def test_teacher_query_surfaces_teacher_magna_carta():
    resp = match_all(
        load_benefits(),
        Criteria(occupation="teacher", employment_status="employed"),
    )
    assert "public-school-teacher-benefits" in _ids(resp.eligible)


def test_student_query_surfaces_education_benefits():
    resp = match_all(load_benefits(), Criteria(age=17, flags=["student"]))
    eligible_ids = _ids(resp.eligible)
    assert {"free-tertiary-education", "dost-st-scholarship",
            "shs-voucher"}.issubset(eligible_ids)


def test_solo_parent_woman_scenario():
    """A 34-y/o employed solo mother in NCR earning 18k."""
    resp = match_all(
        load_benefits(),
        Criteria(
            age=34, gender="female", monthly_income=18000,
            region="NCR", employment_status="employed",
            flags=["solo_parent"],
        ),
    )
    eligible_ids = _ids(resp.eligible)
    # Solo parent benefits and Magna Carta women's special leave should surface.
    assert "solo-parent-benefits" in eligible_ids
    assert "magna-carta-women-special-leave" in eligible_ids
    # Senior discount must NOT appear (age contradicts).
    assert "senior-citizen-discount" not in eligible_ids | _ids(resp.potential)
