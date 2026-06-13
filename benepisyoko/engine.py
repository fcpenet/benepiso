"""The eligibility engine.

Each benefit's :class:`EligibilityRule` is evaluated against the applicant's
:class:`Criteria` one condition at a time. Every condition resolves to one of:

* ``satisfied``    — the criteria meet it.
* ``contradicted`` — the criteria were provided and clearly fail it.
* ``unconfirmed``  — the criteria needed are missing, so we cannot confirm it.

A benefit is **eligible** only when every applicable condition is satisfied.
A benefit is **potential** when nothing contradicts it but something is
unconfirmed — this is what powers discovery of benefits people don't realise
they could claim (e.g. "you'd qualify if you have a Solo Parent ID").
A benefit with any contradicted condition is excluded entirely.
"""

from __future__ import annotations

from .models import (
    Benefit,
    Condition,
    ConditionStatus,
    Criteria,
    EligibilityRule,
    MatchResult,
    QueryResponse,
)

DISCLAIMER = (
    "Informational only — not legal advice. Eligibility rules, amounts and "
    "procedures are simplified and may change; verify with the responsible "
    "agency and the cited law before relying on any result."
)

_SAT = ConditionStatus.satisfied
_UNC = ConditionStatus.unconfirmed
_CON = ConditionStatus.contradicted


def _evaluate(rule: EligibilityRule, c: Criteria) -> list[Condition]:
    conditions: list[Condition] = []
    flags = set(c.flags or [])

    def add(label: str, status: ConditionStatus, detail: str) -> None:
        conditions.append(Condition(label=label, status=status, detail=detail))

    # --- Age ---------------------------------------------------------------
    if rule.min_age is not None:
        if c.age is None:
            add("min_age", _UNC, f"Must be at least {rule.min_age}; age not provided.")
        elif c.age >= rule.min_age:
            add("min_age", _SAT, f"Age {c.age} ≥ {rule.min_age}.")
        else:
            add("min_age", _CON, f"Age {c.age} is below the minimum of {rule.min_age}.")

    if rule.max_age is not None:
        if c.age is None:
            add("max_age", _UNC, f"Must be at most {rule.max_age}; age not provided.")
        elif c.age <= rule.max_age:
            add("max_age", _SAT, f"Age {c.age} ≤ {rule.max_age}.")
        else:
            add("max_age", _CON, f"Age {c.age} is above the maximum of {rule.max_age}.")

    # --- Gender ------------------------------------------------------------
    if rule.gender is not None:
        if c.gender is None:
            add("gender", _UNC, f"For {rule.gender.value} applicants; gender not provided.")
        elif c.gender == rule.gender:
            add("gender", _SAT, f"Gender matches ({rule.gender.value}).")
        else:
            add("gender", _CON, f"Limited to {rule.gender.value} applicants.")

    # --- Income ceiling ----------------------------------------------------
    if rule.max_monthly_income is not None:
        ceil = rule.max_monthly_income
        if c.monthly_income is None:
            add("max_monthly_income", _UNC,
                f"Income must not exceed ₱{ceil:,.0f}/mo; income not provided.")
        elif c.monthly_income <= ceil:
            add("max_monthly_income", _SAT,
                f"Income ₱{c.monthly_income:,.0f} ≤ ₱{ceil:,.0f}.")
        else:
            add("max_monthly_income", _CON,
                f"Income ₱{c.monthly_income:,.0f} exceeds the ₱{ceil:,.0f} ceiling.")

    # --- Employment status -------------------------------------------------
    if rule.employment_statuses:
        allowed = [s.value for s in rule.employment_statuses]
        if c.employment_status is None:
            add("employment_status", _UNC,
                f"Requires status in {allowed}; status not provided.")
        elif c.employment_status.value in allowed:
            add("employment_status", _SAT,
                f"Status '{c.employment_status.value}' is eligible.")
        else:
            add("employment_status", _CON,
                f"Status '{c.employment_status.value}' not among {allowed}.")

    # --- Occupation (line of work) ----------------------------------------
    if rule.occupations:
        if c.occupation is None:
            add("occupation", _UNC,
                f"For {rule.occupations}; line of work not provided.")
        elif c.occupation in rule.occupations:
            add("occupation", _SAT, f"Line of work '{c.occupation}' qualifies.")
        else:
            add("occupation", _CON,
                f"For {rule.occupations}, not '{c.occupation}'.")

    # --- Region ------------------------------------------------------------
    if rule.regions:
        if c.region is None:
            add("region", _UNC,
                f"Available in {rule.regions}; location not provided.")
        elif c.region in rule.regions:
            add("region", _SAT, f"Location '{c.region}' is covered.")
        else:
            add("region", _CON,
                f"Not available in '{c.region}' (covers {rule.regions}).")

    # --- Required flags (ALL) ---------------------------------------------
    for flag in rule.required_flags:
        if flag in flags:
            add(f"flag:{flag}", _SAT, f"Declared '{flag}'.")
        else:
            # Missing flags are unconfirmed, not contradicted: the applicant
            # may simply not have declared it yet. This is core to discovery.
            add(f"flag:{flag}", _UNC, f"Requires '{flag}' — not declared.")

    # --- Any-of flags (at least one) --------------------------------------
    if rule.any_flags:
        present = [f for f in rule.any_flags if f in flags]
        if present:
            add("any_flags", _SAT, f"Declared {present} (one of {rule.any_flags}).")
        else:
            add("any_flags", _UNC,
                f"Requires at least one of {rule.any_flags} — none declared.")

    return conditions


def match_benefit(benefit: Benefit, criteria: Criteria) -> MatchResult:
    conditions = _evaluate(benefit.eligibility, criteria)

    matched = [c.label for c in conditions if c.status == _SAT]
    missing = [c.detail for c in conditions if c.status == _UNC]
    has_contradiction = any(c.status == _CON for c in conditions)

    total = len(conditions)
    score = 1.0 if total == 0 else len(matched) / total
    # Eligible when every applicable condition is satisfied (a benefit with no
    # conditions is universally eligible) and nothing is contradicted.
    eligible = (len(matched) == total) and not has_contradiction

    return MatchResult(
        benefit=benefit,
        eligible=eligible,
        score=round(score, 3),
        conditions=conditions,
        matched=matched,
        missing=missing,
    )


def match_all(benefits: list[Benefit], criteria: Criteria) -> QueryResponse:
    eligible: list[MatchResult] = []
    potential: list[MatchResult] = []

    for benefit in benefits:
        result = match_benefit(benefit, criteria)
        has_contradiction = any(
            c.status == _CON for c in result.conditions
        )
        if result.eligible:
            eligible.append(result)
        elif not has_contradiction:
            potential.append(result)
        # contradicted benefits are dropped

    # Most-confirmed first; nudge lesser-known benefits up so discovery wins ties.
    eligible.sort(key=lambda r: (r.benefit.lesser_known, r.score), reverse=True)
    potential.sort(key=lambda r: (r.score, r.benefit.lesser_known), reverse=True)

    return QueryResponse(
        criteria=criteria,
        eligible=eligible,
        potential=potential,
        disclaimer=DISCLAIMER,
    )
