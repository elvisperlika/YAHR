"""The Ranker's actual work, decoupled from the A2A protocol.

One LLM call: given the orchestrator's bundle (the user's question, the jobs the
Job Searcher found, and optionally the resume Markdown), score each job against
the resume, rank them, and answer the question. No A2A types leak in here, so the
executor only relays whatever this yields.

Idempotent by design: the same bundle should rank the same way every run. Two
levers enforce that — the call is pinned to greedy, seeded sampling
(temperature 0 + a fixed seed), and the prompt spells out a fixed scoring rubric
and a deterministic tie-break so equal cases never reorder. (LLM idempotence is
still best-effort — the provider must honour the seed — but these remove every
source of variation under our control.)
"""

from collections.abc import AsyncIterator

from yahr.config import openrouter_client

# A unit of work the executor relays: (text, is_final) — mirrors job_searcher.
Step = tuple[str, bool]

# ponytail: greedy + a fixed seed is what makes a run reproducible; the prompt
# rules only hold if the sampling itself is pinned. Any constant seed works.
_TEMPERATURE = 0
_SEED = 7

_SYSTEM = (
    "You are a career matching assistant. You are given the user's question, a "
    "list of job postings found for them, and (optionally) their resume in "
    "Markdown. Score each job, rank them best first, then answer the question.\n\n"
    "Follow these rules EXACTLY so the SAME input always yields the SAME output "
    "(deterministic, idempotent ranking):\n"
    "1. Score each job 0-100 with this fixed rubric, applied in this order of "
    "importance: (a) overlap between the resume's skills and the posting's "
    "required skills; (b) relevant experience and seniority; (c) role/domain "
    "match; (d) explicit constraints in the question (location, salary, contract "
    "type). Judge each factor only from the text given.\n"
    "2. Use ONLY the facts in the resume and the postings. Never use outside "
    "knowledge, never invent or assume experience; a fact that is absent counts "
    "as 'not met', never as a guess.\n"
    "3. Rank by score, highest first. Break ties by the order the jobs appear in "
    "the input (earlier wins) — never reorder equal-scored jobs arbitrarily.\n"
    "4. Be consistent: identical input must produce identical scores, identical "
    "order, and identical wording. Do not add variety or hedging between runs.\n"
    "5. If no resume is provided, say so and rank on the postings and the "
    "question alone, applying the same rules.\n\n"
    "Output exactly this and nothing else: a numbered list, best first, each "
    "line as '<rank>. <score>/100 - <job title> - <one-line reason>', then a "
    "final paragraph starting 'Answer:' that addresses the user's question."
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
        # The idempotency knobs: greedy decoding + a fixed seed (see module doc).
        temperature=_TEMPERATURE,
        seed=_SEED,
    )
    yield (reply.choices[0].message.content or "(no answer)"), True


if __name__ == "__main__":
    # ponytail: guard the idempotency wiring — the LLM call must go out with
    # temperature 0 and the fixed seed, and the same input must produce the same
    # outbound request (a regression here silently breaks reproducibility). The
    # prompt rules ride along in _SYSTEM; the model is faked, since real
    # determinism also depends on the provider honouring the seed.
    import asyncio
    from types import SimpleNamespace

    calls: list[dict[str, object]] = []

    def _fake_client() -> tuple[SimpleNamespace, str]:
        def create(**kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            msg = SimpleNamespace(content="1. 90/100 - Dev - fits\nAnswer: that one")
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

        chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        return SimpleNamespace(chat=chat), "fake-model"

    openrouter_client = _fake_client  # type: ignore[assignment]

    async def _demo() -> None:
        bundle = "Question: best fit?\n--- Jobs found ---\n- A\n- B"
        out1 = [s async for s in rank(bundle)]
        out2 = [s async for s in rank(bundle)]

        # Same input -> same steps and the exact same outbound request.
        assert out1 == out2, (out1, out2)
        assert calls[-1] == calls[-2], calls[-2:]

        # The steps: one progress line, then the final answer.
        assert out1[0] == ("Scoring jobs against your resume", False)
        assert out1[-1][1] is True and "90/100" in out1[-1][0], out1[-1]

        # The knobs that actually make it reproducible are wired in.
        sent = calls[-1]
        assert sent["temperature"] == 0, sent
        assert sent["seed"] == _SEED, sent
        assert sent["model"] == "fake-model", sent

    asyncio.run(_demo())
    print("ranker.core self-check ok")
