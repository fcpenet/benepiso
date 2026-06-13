# Benepisyoko

A web app + JSON API that tells a Filipino which government benefits they're
entitled to — **including the lesser-known ones** — based on their age, gender,
income, location, and circumstances. Every benefit comes with the law behind it,
what's required, and how to claim it.

- **Backend:** FastAPI rules engine (Python), served under `/api`.
- **Frontend:** Next.js (React) single-page form + results.
- **Deploy:** one Vercel project — Next.js + the API as a Python serverless function.

> ⚠️ **Not legal advice.** This is a simplified, curated dataset for discovery.
> Amounts, ceilings, and procedures change over time and through implementing
> rules. Always verify against the cited law and the responsible agency.

## How it works

The core is an explainable **rules engine** (no LLM). Each benefit in the corpus
(`benepisyoko/data/benefits.yaml`) declares an eligibility rule. The engine checks an
applicant's criteria against each rule, condition by condition, and sorts results
into two buckets:

- **`eligible`** — every applicable condition is *confirmed*.
- **`potential`** — nothing *contradicts* eligibility, but something is
  unconfirmed (e.g. you didn't say whether you have a Solo Parent ID). This is
  what surfaces benefits people don't know they could claim.

Benefits that are clearly contradicted (e.g. a senior-only benefit for a 30-year-old)
are dropped. Lesser-known benefits are nudged up the rankings.

### Legal provenance & effective dates

Each benefit's `legal_basis` tracks not just the RA number and title, but:

- `effective_date` / `year` — when the law took effect vs. when it was enacted
- `status` — `in_force`, `amended`, `repealed`, or `superseded`
- `amends` — the earlier law it modified
- `amendments[]` — later laws that changed it, each with its own effective date
  and a summary (e.g. RA 11916 raised the senior social pension to ₱1,000,
  *effective January 2024*)
- `source_url` + `last_verified` — entries carrying these have been checked
  against an authoritative source (Official Gazette, lawphil, or the
  administering agency). Entries without them are curated-but-unverified.

## Run it locally

Two processes: the FastAPI backend on `:8000` and the Next.js frontend on
`:3000`. In dev, Next proxies `/api/*` to the backend (see `next.config.js`).

**1. Backend**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # runtime + dev + ingestion deps
uvicorn benepisyoko.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/api/docs

**2. Frontend** (separate terminal)

```bash
npm install
npm run dev
```

Open the app at http://127.0.0.1:3000

## Example (API directly)

```bash
curl -s http://127.0.0.1:8000/api/match -H 'Content-Type: application/json' -d '{
  "age": 34,
  "gender": "female",
  "monthly_income": 18000,
  "region": "NCR",
  "employment_status": "employed",
  "flags": ["solo_parent"]
}' | jq
```

Surfaces, among others, the **Solo Parent cash subsidy & discounts** (RA 11861)
and the **Magna Carta for Women special leave** (RA 9710) — two commonly-missed
entitlements.

## Deploy to Vercel

The repo is a single Vercel project: Next.js builds the frontend, and
`api/index.py` is detected as a **Python serverless function** that re-exports
the FastAPI app. `vercel.json` routes `/api/*` to it and bundles the corpus
(`includeFiles`). The function installs only `requirements.txt` (runtime deps).

```bash
npm i -g vercel
vercel            # first run links/creates the project
vercel --prod     # production deploy
```

No env vars are required. After deploy, the app is at `/`, the API at `/api/*`,
and docs at `/api/docs`. (The ingestion pipeline is a local/build-time tool — it
writes files and isn't run in the serverless environment.)

## Endpoints

All routes are under the `/api` prefix.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/match` | Eligibility check from criteria → `eligible` + `potential` |
| GET | `/api/benefits` | Browse the corpus (filter by `category`, `lesser_known`) |
| GET | `/api/benefits/{id}` | One benefit's full detail |
| GET | `/api/categories` | Available categories |
| GET | `/api/flags` | Recognised special-category flags for `criteria.flags` |
| GET | `/api/occupations` | Recognised lines of work for `criteria.occupation` |
| GET | `/api/docs` | Interactive Swagger docs |

To answer *"what laws help farmers?"*, send just `{"occupation": "farmer"}` to
`/api/match` — the eligible list returns the farmer-specific programs (free
irrigation, RCEF rice support, Sagip Saka) plus anything universal.

## Criteria

| Field | Type | Notes |
| ----- | ---- | ----- |
| `age` | int | |
| `gender` | `male`\|`female` | |
| `monthly_income` | number | gross PHP/month |
| `region` | string | e.g. `NCR` |
| `employment_status` | enum | `employed`, `self_employed`, `unemployed`, `ofw`, `student`, `retired`, `none` |
| `occupation` | string | line of work / sector — see `GET /occupations` |
| `flags` | string[] | declared categories — see `GET /flags` |

## Grounding the corpus in real law text (ingestion pipeline)

The benefits corpus is hand-curated, but the laws it cites can be fetched in
full from [LawPhil](https://lawphil.net) and stored locally, so each entry is
backed by — and checkable against — the actual statute rather than recall.

```bash
python -m ingest.cli --list            # show every target law (fetch nothing)
python -m ingest.cli --all             # fetch all RAs the corpus cites (+ seeds)
python -m ingest.cli --all --limit 3   # small first run
python -m ingest.cli --ra 11916 --year 2022   # one law
python -m ingest.cli --status          # summarise what's stored
python -m ingest.cli --link            # corpus citation -> ingested-text coverage
```

How it works:

- **Targets are derived from the corpus** ([ingest/registry.py](ingest/registry.py)) —
  every RA a benefit cites becomes a target, so the law store stays in sync.
  `EXTRA_SEEDS` lets you pre-fetch laws ahead of adding their benefits.
- **Polite fetching** ([ingest/fetcher.py](ingest/fetcher.py)) — descriptive
  User-Agent, configurable `--delay` between requests (default 2s), retries with
  backoff.
- **Parsing** ([ingest/parser.py](ingest/parser.py)) — byte-level charset
  detection (legacy encodings), markup stripped, LawPhil watermark tokens
  removed, a `looks_like_law` sanity check flags pages that aren't statutes.
- **Idempotent + auditable** ([ingest/pipeline.py](ingest/pipeline.py)) — texts
  land in `benepisyoko/data/laws/RA-<num>-<year>.txt`; a `manifest.json` records the URL,
  fetch time, char count and a SHA-256 of each. Existing texts are skipped unless
  `--force`.

Stored law text is the foundation for the planned RAG layer and for verifying
the curated eligibility rules against statutory language.

> **Note:** LawPhil is a free, public legal archive; this fetches only the
> public statute pages, rate-limited. It does not cover *implementing rules
> (IRRs)*, where many operative amounts/procedures actually live — those remain
> a manual verification step for now.

## Adding a benefit

Append an entry to `benepisyoko/data/benefits.yaml` following the existing shape. No code
changes needed — it's validated against the `Benefit` model on load. Favour
recent, in-force laws and accurate RA citations.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Layout

```
benepisyoko/         Python backend package
  main.py            FastAPI routes (mounted under /api)
  models.py          Pydantic models (criteria, benefit, results) + vocab
  engine.py          eligibility evaluation
  repository.py      loads/caches the YAML corpus
  data/
    benefits.yaml    the curated corpus  <-- edit this to grow coverage
    laws/            ingested full statute text + manifest.json
api/
  index.py           Vercel serverless entry (re-exports the FastAPI app)
ingest/              law-text ingestion pipeline (local/build-time tool)
  sources.py · registry.py · fetcher.py · parser.py · pipeline.py · cli.py
src/app/             Next.js frontend (App Router)
  page.tsx           the form + results UI (client component)
  layout.tsx · globals.css
tests/
  test_engine.py · test_ingest.py
vercel.json          routes /api/* to the Python function + bundles the corpus
next.config.js       dev proxy: /api/* -> FastAPI on :8000
requirements.txt     runtime deps (used by the Vercel function)
requirements-dev.txt  + uvicorn, pytest, httpx, bs4, lxml (local + ingestion)
```

## Roadmap

- Expand the corpus (LGU-specific benefits, GSIS, veterans, PWD/IP-specific laws).
- Optional RAG layer over the ingested RA texts for the long tail of provisions.
- Ingest implementing rules (IRRs), where many operative amounts actually live.
- Localisation (Filipino) of descriptions and claim steps.
