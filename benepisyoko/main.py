"""Benepisyoko API — discover the Philippine benefits you're entitled to.

All routes are served under the ``/api`` prefix so the same app works locally
(``uvicorn benepisyoko.main:app`` → http://localhost:8000/api/...) and as a
Vercel Python serverless function (which receives requests at ``/api/*``).
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .engine import DISCLAIMER, match_all
from .models import (
    AskRequest,
    AskResponse,
    Benefit,
    Criteria,
    KNOWN_FLAGS,
    KNOWN_OCCUPATIONS,
    QueryResponse,
    Source,
)
from .rag.generator import generate_answer
from .rag.retriever import search as retrieve
from .repository import categories, get_benefit, load_benefits

app = FastAPI(
    title="Benepisyoko",
    version=__version__,
    description=(
        "Discover the government benefits a Filipino is entitled to — including "
        "lesser-known ones — based on age, gender, income, location and special "
        "circumstances, with the law behind each and how to claim it.\n\n"
        + DISCLAIMER
    ),
    # Keep docs/openapi under /api so they're reachable through the function.
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# The frontend is same-origin in production; CORS is permissive to ease local
# dev and any external clients hitting the JSON API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


@api.get("", tags=["meta"])
def root() -> dict:
    return {
        "service": "Benepisyoko",
        "version": __version__,
        "benefits_loaded": len(load_benefits()),
        "endpoints": {
            "match": "POST /api/match",
            "benefits": "GET /api/benefits",
            "benefit": "GET /api/benefits/{id}",
            "categories": "GET /api/categories",
            "flags": "GET /api/flags",
            "occupations": "GET /api/occupations",
            "ask": "POST /api/ask",
            "docs": "GET /api/docs",
        },
        "disclaimer": DISCLAIMER,
    }


@api.post("/match", response_model=QueryResponse, tags=["match"])
def match(criteria: Criteria) -> QueryResponse:
    """Return benefits split into `eligible` (all conditions confirmed) and
    `potential` (not disqualified — would qualify on meeting the listed items)."""
    return match_all(load_benefits(), criteria)


@api.get("/benefits", response_model=list[Benefit], tags=["catalog"])
def list_benefits(
    category: str | None = Query(None, description="Filter by category."),
    lesser_known: bool | None = Query(
        None, description="If set, return only lesser-known (or well-known) benefits."
    ),
) -> list[Benefit]:
    results = load_benefits()
    if category is not None:
        results = [b for b in results if b.category == category]
    if lesser_known is not None:
        results = [b for b in results if b.lesser_known == lesser_known]
    return results


@api.get("/benefits/{benefit_id}", response_model=Benefit, tags=["catalog"])
def read_benefit(benefit_id: str) -> Benefit:
    benefit = get_benefit(benefit_id)
    if benefit is None:
        raise HTTPException(status_code=404, detail=f"No benefit with id '{benefit_id}'.")
    return benefit


@api.get("/categories", response_model=list[str], tags=["catalog"])
def list_categories() -> list[str]:
    return categories()


@api.get("/flags", tags=["catalog"])
def list_flags() -> dict[str, str]:
    """The special-category flags an applicant can declare in `criteria.flags`."""
    return KNOWN_FLAGS


@api.get("/occupations", tags=["catalog"])
def list_occupations() -> dict[str, str]:
    """The recognised lines of work for `criteria.occupation`."""
    return KNOWN_OCCUPATIONS


@api.post("/ask", response_model=AskResponse, tags=["rag"])
def ask(req: AskRequest) -> AskResponse:
    """Ask a free-text question about Philippine benefits/law.

    Retrieves the most relevant passages from the ingested statute texts and —
    when an `ANTHROPIC_API_KEY` is configured — returns a Claude-synthesised,
    citation-grounded answer. Without a key, `answer` is null and the retrieved
    passages are returned for the caller to read (extractive mode)."""
    hits = retrieve(req.question, top_k=req.top_k)
    sources = [
        Source(
            law=chunk.law,
            title=chunk.title,
            year=chunk.year,
            section=chunk.section,
            source_url=chunk.source_url,
            score=round(score, 4),
            excerpt=chunk.text[:400] + ("…" if len(chunk.text) > 400 else ""),
        )
        for chunk, score in hits
    ]
    answer = generate_answer(req.question, [s.model_dump() for s in sources])
    return AskResponse(
        question=req.question,
        answer=answer,
        llm_used=answer is not None,
        sources=sources,
        disclaimer=DISCLAIMER,
    )


app.include_router(api)
