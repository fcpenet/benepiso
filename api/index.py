"""Vercel Python serverless entrypoint.

Vercel's Python runtime serves the ASGI application exported here as `app`.
Requests arrive under `/api/*` (see vercel.json rewrites), which is exactly the
prefix the FastAPI routes are mounted on, so no path rewriting is needed.
"""

from benepisyoko.main import app  # noqa: F401  (re-exported for Vercel)
