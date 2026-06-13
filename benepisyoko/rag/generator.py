"""Optional answer synthesis with Claude, grounded in retrieved statute text.

Gated behind ANTHROPIC_API_KEY: when the key (and the `anthropic` SDK) are
present, this turns the top retrieved passages into a concise, cited answer.
When either is missing it returns ``None`` and the API falls back to returning
the passages directly. The model is instructed to answer *only* from the
provided excerpts and to cite them, so it can't invent law.
"""

from __future__ import annotations

import os

MODEL = "claude-opus-4-8"

_SYSTEM = (
    "You answer questions about Philippine law using ONLY the numbered statute "
    "excerpts provided by the user. Rules:\n"
    "- Base every statement strictly on the excerpts. Do not use outside knowledge.\n"
    "- Cite the excerpts you rely on inline as [n], and name the Republic Act and "
    "section (e.g. 'RA 11210, Sec. 5').\n"
    "- If the excerpts do not contain the answer, say so plainly and suggest what "
    "to look for — do not guess.\n"
    "- Be concise and practical. This is general information, not legal advice."
)


def generate_answer(question: str, sources: list[dict]) -> str | None:
    """Return a cited answer, or None if generation is unavailable/unconfigured."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    if not sources:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    context = "\n\n".join(
        f"[{i + 1}] {s['law']} ({s['year']}) — {s['section']}\n{s['text']}"
        for i, s in enumerate(sources)
    )

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\n"
                        f"Statute excerpts:\n{context}"
                    ),
                }
            ],
        )
    except Exception:
        # Network/auth/rate-limit issues should degrade to extractive mode,
        # never crash the endpoint.
        return None

    return "".join(b.text for b in message.content if b.type == "text").strip() or None
