"""The CV Assistant's actual work, decoupled from the A2A protocol.

One LLM call: given the orchestrator's bundle (the user's request, the jobs the
Job Searcher found, and optionally the resume Markdown), pick the single job the
user named, compare it against the resume, and return a gap analysis plus
concrete suggestions to strengthen the resume for that job. No A2A types leak in
here, so the executor only relays whatever this yields.

Unlike the four (planned) section assistants, this agent is advisory and may
surface skills the resume lacks — it analyses the gap, it does not rewrite the
resume, so it is allowed to recommend acquiring things that aren't there yet.

Idempotent by design (mirrors ranker.core): the same bundle should advise the
same way every run. The call is pinned to greedy, seeded sampling (temperature 0
+ a fixed seed) and the prompt asks for deterministic wording. (LLM idempotence
is still best-effort — the provider must honour the seed.)
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
    "You are a resume coach. You are given the user's request, a list of job "
    "postings found for them, and (optionally) their resume in Markdown. Your job "
    "is to analyse the gap between the resume and the ONE job the user is asking "
    "about, then give concrete suggestions to strengthen the resume for it.\n\n"
    "Follow these rules EXACTLY so the SAME input always yields the SAME output "
    "(deterministic, idempotent advice):\n"
    "1. Identify the SINGLE target job: match the title and/or company named in "
    "the user's request against the postings. If the request is ambiguous or "
    "names no job, use the first posting in the list.\n"
    "2. If no resume is provided, say so in one line and stop — do not invent a "
    "resume or guess its contents.\n"
    "3. Produce a '## Gaps' section: skills, keywords, tools, and requirements "
    "the posting asks for that the resume does not clearly show. For each, mark "
    "whether it can be addressed by rewording a fact already in the resume "
    "(REWORD) or genuinely needs to be acquired (ACQUIRE).\n"
    "4. Produce a '## Suggestions' section: concrete, specific edits to "
    "strengthen the resume for THIS job — reword X to match the posting's "
    "wording, quantify Y, surface Z that is buried. When you claim the user "
    "already has something, use ONLY facts present in the resume; you MAY "
    "recommend acquiring skills the resume lacks, but label those clearly so "
    "they are never mistaken for existing experience.\n"
    "5. Be consistent: identical input must produce identical wording, order, "
    "and recommendations. Do not add variety or hedging between runs.\n\n"
    "Output Markdown with a one-line header naming the target job, then the "
    "'## Gaps' and '## Suggestions' sections, and nothing else."
)


async def analyze(message: str) -> AsyncIterator[Step]:
    """Analyse the gap between the resume and the named job, and suggest fixes.

    Args:
        message: The orchestrator's bundle — the user's request, the jobs the
            Job Searcher found, and optionally the resume Markdown.

    Yields:
        (text, is_final) steps: one progress line, then the final gap report.
    """
    yield "Analyzing the gap with your resume", False
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
    yield (reply.choices[0].message.content or "(no suggestions)"), True


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
            msg = SimpleNamespace(content="## Gaps\n- Kubernetes (ACQUIRE)")
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

        chat = SimpleNamespace(completions=SimpleNamespace(create=create))
        return SimpleNamespace(chat=chat), "fake-model"

    openrouter_client = _fake_client  # type: ignore[assignment]

    async def _demo() -> None:
        bundle = "Request: strengthen for Dev\n--- Jobs found ---\n- Dev\n--- Resume ---\n# CV"
        out1 = [s async for s in analyze(bundle)]
        out2 = [s async for s in analyze(bundle)]

        # Same input -> same steps and the exact same outbound request.
        assert out1 == out2, (out1, out2)
        assert calls[-1] == calls[-2], calls[-2:]

        # The steps: one progress line, then the final report.
        assert out1[0] == ("Analyzing the gap with your resume", False)
        assert out1[-1][1] is True and "## Gaps" in out1[-1][0], out1[-1]

        # The knobs that actually make it reproducible are wired in.
        sent = calls[-1]
        assert sent["temperature"] == 0, sent
        assert sent["seed"] == _SEED, sent
        assert sent["model"] == "fake-model", sent

    asyncio.run(_demo())
    print("cv_assistant.core self-check ok")
