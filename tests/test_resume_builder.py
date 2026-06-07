"""Tests for the Resume Builder agent.

Runnable without pytest:  ``python tests/test_resume_builder.py``
(or with pytest if it is installed).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from a2a.helpers.proto_helpers import (
    get_data_parts,
    get_text_parts,
    new_text_message,
)
from a2a.types import Role, TaskState

from agents.resume_builder.agent_card import build_agent_card
from agents.resume_builder.config import OpenRouterConfig
from agents.resume_builder.core import (
    _extract_json_object,
    build_resume_from_markdown,
    resume_from_dict,
)
from agents.resume_builder.executor import ResumeBuilderExecutor, _resolve_markdown

SAMPLE_JSON = {
    "personal_info": {
        "name": "Elvis Perlika",
        "email": "elvis@example.com",
        "github": "github.com/elvisperlika",
    },
    "education": [{"degree": "MSc CS", "institution": "Bologna", "location": "Cesena"}],
    "work_experience": [
        {
            "title": "Java Developer",
            "company": "CP Sistemi",
            "period": "May 2024 - Jul 2024",
            "skills": ["Java", "IoT", ""],  # blank entry should be dropped
        }
    ],
    "projects": [{"name": "ByTrail", "technologies": ["Vue", "Node.js"]}],
    "skills": {
        "hard": ["Scala", "Python"],
        "soft": ["Teamwork"],
        "languages": ["Italian"],
    },
}


def test_extract_json_object_handles_fences():
    raw = '```json\n{"a": 1}\n```'
    assert _extract_json_object(raw) == {"a": 1}
    assert _extract_json_object('{"a": 1}') == {"a": 1}
    assert _extract_json_object('prose {"a": 1} more') == {"a": 1}


def test_resume_from_dict_maps_fields():
    resume = resume_from_dict(SAMPLE_JSON, raw_text="# md")
    assert resume.personal_info.name == "Elvis Perlika"
    assert resume.personal_info.phone == ""  # missing -> empty
    assert resume.work_experience[0].skills == ["Java", "IoT"]  # blank dropped
    assert resume.skills.hard == ["Scala", "Python"]
    assert resume.projects[0].technologies == ["Vue", "Node.js"]
    assert resume.raw_text == "# md"


class _FakeChatCompletions:
    def __init__(self, content: str):
        self._content = content

    async def create(self, **kwargs):
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _FakeClient:
    def __init__(self, content: str):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(content))

    async def close(self):  # pragma: no cover - not called (caller owns client)
        pass


def test_build_resume_from_markdown_with_fake_client():
    client = _FakeClient(json.dumps(SAMPLE_JSON))
    config = OpenRouterConfig(
        api_key="test", base_url="http://test", model="test/model"
    )
    resume = asyncio.run(
        build_resume_from_markdown("# resume", config=config, client=client)
    )
    assert resume.personal_info.name == "Elvis Perlika"
    assert resume.raw_text == "# resume"


def test_agent_card():
    card = build_agent_card("http://localhost:8001/")
    assert card.name == "Resume Builder"
    assert card.skills[0].id == "build_resume"
    assert card.supported_interfaces[0].url == "http://localhost:8001/"


def test_resolve_markdown_from_text():
    msg = new_text_message("# Just markdown\n\nbody", role=Role.ROLE_USER)
    ctx = SimpleNamespace(message=msg)
    assert _resolve_markdown(ctx) == "# Just markdown\n\nbody"


class _FakeQueue:
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


def test_executor_emits_artifact_and_completes(monkeypatch):
    async def fake_build(markdown, config=None):
        return resume_from_dict(SAMPLE_JSON, raw_text=markdown)

    monkeypatch.setattr(
        "agents.resume_builder.executor.build_resume_from_markdown", fake_build
    )

    msg = new_text_message("# resume markdown", role=Role.ROLE_USER)
    ctx = SimpleNamespace(task_id="t1", context_id="c1", current_task=None, message=msg)
    queue = _FakeQueue()

    asyncio.run(ResumeBuilderExecutor().execute(ctx, queue))

    artifact_events = [
        e for e in queue.events if e.__class__.__name__ == "TaskArtifactUpdateEvent"
    ]
    assert artifact_events, "expected an artifact event"
    data = get_data_parts(artifact_events[0].artifact.parts)[0]
    assert data["personal_info"]["name"] == "Elvis Perlika"

    status_events = [
        e for e in queue.events if e.__class__.__name__ == "TaskStatusUpdateEvent"
    ]
    assert status_events[-1].status.state == TaskState.TASK_STATE_COMPLETED
    summary = get_text_parts(status_events[-1].status.message.parts)[0]
    assert "Elvis Perlika" in summary


def test_jsonrpc_send_message_round_trip(monkeypatch):
    """End-to-end: a SendMessage JSON-RPC call returns a completed task whose
    artifact carries the structured resume."""
    import warnings

    from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, VERSION_HEADER
    from starlette.testclient import TestClient

    from agents.resume_builder.server import build_app

    async def fake_build(markdown, config=None):
        return resume_from_dict(SAMPLE_JSON, raw_text=markdown)

    monkeypatch.setattr(
        "agents.resume_builder.executor.build_resume_from_markdown", fake_build
    )

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "ROLE_USER",
                "parts": [{"text": "# resume"}],
                "messageId": "m1",
            }
        },
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with TestClient(build_app()) as client:
            resp = client.post(
                "/",
                json=payload,
                headers={VERSION_HEADER: PROTOCOL_VERSION_CURRENT},
            )

    body = resp.json()
    assert "error" not in body, body.get("error")
    task = body["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    artifact = task["artifacts"][0]
    assert artifact["name"] == "resume"
    assert artifact["parts"][0]["data"]["personal_info"]["name"] == "Elvis Perlika"


# --- minimal runner so the file works without pytest -------------------------


class _MonkeyPatch:
    """Tiny subset of pytest's monkeypatch for the standalone runner."""

    def __init__(self):
        self._undo = []

    def setattr(self, target: str, value):
        module_path, attr = target.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        old = getattr(module, attr)
        self._undo.append((module, attr, old))
        setattr(module, attr, value)

    def undo(self):
        for module, attr, old in reversed(self._undo):
            setattr(module, attr, old)
        self._undo.clear()


def _run():
    import inspect

    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    failures = 0
    for name, fn in tests:
        mp = _MonkeyPatch()
        try:
            if "monkeypatch" in inspect.signature(fn).parameters:
                fn(mp)
            else:
                fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}: {exc!r}")
        finally:
            mp.undo()
    if failures:
        raise SystemExit(f"{failures} test(s) failed")
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == "__main__":
    _run()
