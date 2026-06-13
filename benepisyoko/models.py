"""Pydantic models for criteria, the benefit corpus, and match results."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Gender(str, Enum):
    male = "male"
    female = "female"


class EmploymentStatus(str, Enum):
    employed = "employed"
    self_employed = "self_employed"
    unemployed = "unemployed"
    ofw = "ofw"
    student = "student"
    retired = "retired"
    none = "none"


# Vocabulary of special-category flags an applicant can declare. Benefits
# reference these in their eligibility rules. Keeping this open-ended (plain
# strings) lets the corpus grow without code changes, but these are the
# currently-recognised ones, surfaced via GET /flags.
KNOWN_FLAGS: dict[str, str] = {
    "indigent": "Classified poor / low-income (e.g. listed in DSWD Listahanan).",
    "pwd": "Person with disability with a valid PWD ID.",
    "solo_parent": "Solo parent with a valid Solo Parent ID.",
    "pregnant": "Currently pregnant or recently gave birth.",
    "new_father": "Father of a newly delivered child.",
    "married": "Legally married.",
    "student": "Currently enrolled in a tertiary education institution.",
    "first_time_jobseeker": "Looking for a job for the first time.",
    "sss_member": "Active or contributing SSS member.",
    "involuntary_separation": "Lost a job through no fault of their own (retrenchment, closure, etc.).",
    "has_children": "Has dependent children.",
    "low_consumption_household": "Household consuming a small amount of electricity per month.",
    "agrarian_reform_beneficiary": "Awarded land under the Comprehensive Agrarian Reform Program.",
    "foster_parent": "Licensed foster parent caring for a foster child.",
}

# Vocabulary of "line of work" / sector. Unlike employment_status (which says
# *whether* someone works), occupation says *what* they do — the axis that
# surfaces sector-specific laws (e.g. laws passed to help farmers). Surfaced via
# GET /occupations.
KNOWN_OCCUPATIONS: dict[str, str] = {
    "farmer": "Farmer / palay grower / agrarian reform beneficiary.",
    "fisherfolk": "Fisherfolk / municipal or small-scale fisher.",
    "domestic_worker": "Kasambahay — household helper, yaya, cook, etc.",
    "ofw": "Overseas Filipino Worker (land-based).",
    "seafarer": "Sea-based overseas worker / merchant mariner.",
    "teacher": "Public or private school teacher.",
    "health_worker": "Public health worker (nurse, doctor, midwife, etc.).",
    "government_employee": "Employee of a government agency or GOCC.",
    "private_employee": "Rank-and-file employee in the private sector.",
    "driver": "Public utility / TNVS driver or operator.",
    "informal_worker": "Worker in the informal economy (vendor, freelancer, etc.).",
}


class Criteria(BaseModel):
    """What we know about the applicant. Everything is optional — the more
    that is supplied, the more confidently benefits can be confirmed."""

    age: Optional[int] = Field(None, ge=0, le=130)
    gender: Optional[Gender] = None
    monthly_income: Optional[float] = Field(
        None, ge=0, description="Gross monthly income in PHP."
    )
    region: Optional[str] = Field(
        None, description="Region/province, e.g. 'NCR', 'Region IV-A'."
    )
    employment_status: Optional[EmploymentStatus] = None
    occupation: Optional[str] = Field(
        None,
        description="Line of work / sector, e.g. 'farmer'. See GET /occupations.",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Declared special categories, e.g. ['solo_parent', 'pwd']. See GET /flags.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "age": 34,
                "gender": "female",
                "monthly_income": 18000,
                "region": "NCR",
                "employment_status": "employed",
                "occupation": "farmer",
                "flags": ["solo_parent"],
            }
        }
    }


class LawStatus(str, Enum):
    in_force = "in_force"
    amended = "amended"  # still in force but modified by a later law
    repealed = "repealed"
    superseded = "superseded"


class Amendment(BaseModel):
    law: str = Field(..., description="The amending law, e.g. 'RA 11916'.")
    year: int
    summary: Optional[str] = Field(
        None, description="What this amendment changed (e.g. raised the amount)."
    )
    effective_date: Optional[str] = Field(
        None, description="ISO date (YYYY-MM-DD) or year the amendment took effect."
    )


class LegalBasis(BaseModel):
    law: str = Field(..., description="Republic Act / PD number, e.g. 'RA 9994'.")
    title: str
    year: int = Field(..., description="Year of enactment / approval.")
    citation: Optional[str] = Field(
        None, description="Specific section or implementing rule, if relevant."
    )
    effective_date: Optional[str] = Field(
        None, description="ISO date (YYYY-MM-DD) or year the law took effect."
    )
    status: LawStatus = Field(
        LawStatus.in_force, description="Current standing of this legal basis."
    )
    authors: list[str] = Field(
        default_factory=list,
        description="Principal author(s)/sponsor(s), e.g. ['Sen. Risa Hontiveros'].",
    )
    amends: Optional[str] = Field(
        None, description="Earlier law this one amends/repeals, e.g. 'RA 8972'."
    )
    amendments: list[Amendment] = Field(
        default_factory=list,
        description="Later laws that amended this one, newest first.",
    )
    source_url: Optional[str] = Field(
        None, description="Authoritative source for the citation (e.g. Official Gazette)."
    )
    last_verified: Optional[str] = Field(
        None, description="ISO date the entry was last checked against sources."
    )


class EligibilityRule(BaseModel):
    """A benefit's eligibility. Any field left unset is simply not required."""

    min_age: Optional[int] = None
    max_age: Optional[int] = None
    gender: Optional[Gender] = None
    max_monthly_income: Optional[float] = Field(
        None, description="Income ceiling for means-tested benefits."
    )
    employment_statuses: Optional[list[EmploymentStatus]] = Field(
        None, description="Applicant's status must be one of these, if set."
    )
    occupations: Optional[list[str]] = Field(
        None, description="Limited to these lines of work; None means any."
    )
    required_flags: list[str] = Field(
        default_factory=list, description="ALL of these flags must apply."
    )
    any_flags: list[str] = Field(
        default_factory=list, description="At least ONE of these flags must apply."
    )
    regions: Optional[list[str]] = Field(
        None, description="Geographically limited; None means nationwide."
    )


class Benefit(BaseModel):
    id: str
    name: str
    short_name: Optional[str] = None
    category: str
    description: str
    benefit_value: str = Field(..., description="What the beneficiary actually gets.")
    legal_basis: LegalBasis
    eligibility: EligibilityRule
    requirements: list[str] = Field(default_factory=list)
    how_to_claim: list[str] = Field(default_factory=list)
    where_to_apply: Optional[str] = None
    lesser_known: bool = False
    notes: Optional[str] = None


class ConditionStatus(str, Enum):
    satisfied = "satisfied"
    unconfirmed = "unconfirmed"  # criteria missing — could still qualify
    contradicted = "contradicted"  # criteria provided and clearly fails


class Condition(BaseModel):
    label: str
    status: ConditionStatus
    detail: str


class MatchResult(BaseModel):
    benefit: Benefit
    eligible: bool
    score: float = Field(..., description="Fraction of applicable conditions satisfied.")
    conditions: list[Condition]
    matched: list[str]
    missing: list[str] = Field(
        default_factory=list, description="What to confirm/meet to qualify."
    )


class QueryResponse(BaseModel):
    criteria: Criteria
    eligible: list[MatchResult] = Field(
        default_factory=list, description="All conditions confirmed."
    )
    potential: list[MatchResult] = Field(
        default_factory=list,
        description="Not disqualified — would qualify on meeting/declaring the missing items.",
    )
    disclaimer: str


# --- Retrieval-augmented Q&A over the ingested statute texts ------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="A question about PH benefits/law.")
    top_k: int = Field(5, ge=1, le=12, description="How many statute passages to retrieve.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "How many days of paid maternity leave am I entitled to?",
                "top_k": 5,
            }
        }
    }


class Source(BaseModel):
    law: str
    title: str
    year: int
    section: str
    source_url: Optional[str] = None
    score: float = Field(..., description="Relevance score (higher = closer match).")
    excerpt: str


class AskResponse(BaseModel):
    question: str
    answer: Optional[str] = Field(
        None,
        description="Cited answer synthesised from the passages (null in extractive mode).",
    )
    llm_used: bool = Field(
        ..., description="Whether a Claude-generated answer was produced."
    )
    sources: list[Source] = Field(
        default_factory=list, description="Retrieved statute passages, most relevant first."
    )
    disclaimer: str
