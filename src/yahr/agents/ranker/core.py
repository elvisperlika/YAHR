"""The Ranker's actual work, decoupled from the A2A protocol.

One LLM call: given the orchestrator's bundle (the user's question, the jobs the
Job Searcher found, and optionally the resume Markdown), score each job against
the resume, rank them, and answer the question. No A2A types leak in here, so the
executor only relays whatever this yields.
"""

from collections.abc import AsyncIterator

from yahr.config import openrouter_client

# A unit of work the executor relays: (text, is_final) — mirrors job_searcher.
Step = tuple[str, bool]

_SYSTEM = (
    "You are a career matching assistant. You are given the user's question, a "
    "list of job postings found for them, and (optionally) their resume in "
    "Markdown. Score each job's fit against the resume from 0-100, rank them best "
    "first with a one-line reason each, then answer the user's question. Use ONLY "
    "the facts in the resume and the postings — never invent experience. If no "
    "resume is provided, say so and rank on the postings alone."
)


async def rank(message: str) -> AsyncIterator[Step]:
    """Score the found jobs against the resume and answer the user's question.

    Args:
        message: The orchestrator's bundle — the user's question, the jobs the
            Job Searcher found, and optionally the resume Markdown.

    Yields:
        (text, is_final) steps: one progress line, then the final answer.
    """
    yield "Scoring jobs against your resume", False
    # ponytail: blocking LLM call inside async — fine for a single-client CLI
    # agent; wrap in asyncio.to_thread if it ever serves concurrent tasks.
    client, model = openrouter_client()
    reply = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": message},
        ],
    )
    yield (reply.choices[0].message.content or "(no answer)"), True
