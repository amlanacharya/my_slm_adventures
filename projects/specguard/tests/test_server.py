from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from specguard.server import create_app


FULL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n\n## Users\nText.\n\n"
    "## Requirements\nText.\n\n## Success Metrics\nText.\n\n## Risks and Assumptions\nText.\n"
)
PARTIAL_DOC = (
    "# Product Requirements Document\n\n"
    "## Problem\nText.\n\n## Goals\nText.\n"
)

PASS_JSON = json.dumps({"verdict": "pass", "criteria": [], "notes": "ok"})
FAIL_JSON = json.dumps({"verdict": "needs_revision", "criteria": [], "notes": "missing sections"})


class FakeChatModel:
    """Routes by system message role: planner → brief, critic → JSON, writer → docs."""

    def __init__(self):
        self._critic_index = 0
        self._critic_replies = [FAIL_JSON, PASS_JSON]
        self._drafts = [PARTIAL_DOC, FULL_DOC]

    def invoke(self, messages):
        system = messages[0].content if messages else ""
        if "planner" in system.lower():
            return _ai("Brief: keep it concrete.")
        if "critic" in system.lower():
            idx = self._critic_index
            self._critic_index += 1
            reply = self._critic_replies[idx] if idx < len(self._critic_replies) else self._critic_replies[-1]
            return _ai(reply)
        return _ai(self._drafts.pop(0) if self._drafts else FULL_DOC)


def _ai(content: str):
    from langchain_core.messages import AIMessage

    return AIMessage(content=content)


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SPECGUARD_OUTPUT_DIR", str(tmp_path))
    # Disable opening a browser during the test.
    monkeypatch.setenv("SPECGUARD_NO_BROWSER", "1")
    app = create_app(chat_model_factory=lambda: FakeChatModel())
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_settings_endpoint_returns_provider_and_model(client, monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "ollama")
    monkeypatch.setenv("SPECGUARD_MODEL", "gemma4:latest")
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "ollama"
    assert body["model"] == "gemma4:latest"
    assert "ollama_base_url" in body
    assert "has_openai_key" in body
    assert "has_anthropic_key" in body
    assert "has_minimax_key" in body
    assert "minimax_base_url" in body


def test_settings_update_persists_to_disk(client, tmp_path):
    """Switching providers + changing the model writes to settings.json so a
    server restart sees the new values."""
    import json
    settings_file = tmp_path / "settings.json"
    # Re-bind the module-level ENV_PATH-equivalent by setting the env var that
    # persistence._settings_path() reads.
    import os
    old = os.environ.get("SPECGUARD_SETTINGS_FILE")
    os.environ["SPECGUARD_SETTINGS_FILE"] = str(settings_file)
    try:
        r = client.post("/api/settings", json={"provider": "openai", "model": "gpt-4.1-mini"})
        assert r.status_code == 200
        assert r.json()["provider"] == "openai"
        assert r.json()["model"] == "gpt-4.1-mini"
        # settings.json should now exist on disk.
        assert settings_file.exists()
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4.1-mini"
    finally:
        if old is None:
            os.environ.pop("SPECGUARD_SETTINGS_FILE", None)
        else:
            os.environ["SPECGUARD_SETTINGS_FILE"] = old


def test_api_key_endpoint_saves_to_env(client, tmp_path, monkeypatch):
    """Setting an OpenAI key writes OPENAI_API_KEY=... to .env and updates os.environ."""
    env_path = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)
    # persistence.read_env_var / write_env_var read .env from the cwd.
    r = client.post(
        "/api/api-key",
        json={"provider": "openai", "key": "sk-test-1234"},
    )
    assert r.status_code == 200
    assert r.json()["configured"] is True
    assert env_path.exists()
    assert "OPENAI_API_KEY=sk-test-1234" in env_path.read_text(encoding="utf-8")
    # Subsequent GET settings reports has_openai_key=True.
    r2 = client.get("/api/settings")
    assert r2.json()["has_openai_key"] is True


def test_minimax_api_key_endpoint_saves_to_env(client, tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)

    r = client.post(
        "/api/api-key",
        json={"provider": "minimax", "key": "sk-minimax-1234"},
    )

    assert r.status_code == 200
    assert r.json()["configured"] is True
    assert "MINIMAX_API_KEY=sk-minimax-1234" in env_path.read_text(encoding="utf-8")
    assert client.get("/api/settings").json()["has_minimax_key"] is True


def test_api_key_clear_removes_from_env(client, tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=old-value\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = client.post("/api/api-key", json={"provider": "openai", "key": "x", "clear": True})
    assert r.status_code == 200
    assert "OPENAI_API_KEY" not in env_path.read_text(encoding="utf-8")


def test_api_key_rejects_unknown_provider(client):
    r = client.post("/api/api-key", json={"provider": "google", "key": "x"})
    assert r.status_code == 400


def test_api_key_rejects_empty_key(client):
    r = client.post("/api/api-key", json={"provider": "openai", "key": "  "})
    assert r.status_code == 400


def test_switching_provider_snaps_model_to_default(client, tmp_path):
    """Switching from ollama to openai should auto-set the model to gpt-4.1-mini
    unless the user also explicitly passes a model in the same request."""
    import os
    settings_file = tmp_path / "settings.json"
    old = os.environ.get("SPECGUARD_SETTINGS_FILE")
    os.environ["SPECGUARD_SETTINGS_FILE"] = str(settings_file)
    try:
        r = client.post("/api/settings", json={"provider": "openai"})
        assert r.json()["model"] == "gpt-4.1-mini"
        r = client.post("/api/settings", json={"provider": "anthropic"})
        assert r.json()["model"] == "claude-3-5-haiku-latest"
        r = client.post("/api/settings", json={"provider": "minimax"})
        assert r.json()["model"] == "MiniMax-M3"
        # And ollama snaps back to gemma4:latest.
        r = client.post("/api/settings", json={"provider": "ollama"})
        assert r.json()["model"] == "gemma4:latest"
    finally:
        if old is None:
            os.environ.pop("SPECGUARD_SETTINGS_FILE", None)
        else:
            os.environ["SPECGUARD_SETTINGS_FILE"] = old


def test_modes_endpoint_lists_supported_modes(client):
    r = client.get("/api/modes")
    assert r.status_code == 200
    body = r.json()
    assert {m["name"] for m in body["modes"]} == {"prd", "brd", "tech_scope"}
    for mode in body["modes"]:
        assert "label" in mode and "sections" in mode
        assert len(mode["sections"]) >= 5


def test_generate_endpoint_streams_sse_events(client):
    r = client.post(
        "/api/generate",
        json={"idea": "Build an app for interior designers.", "mode": "prd"},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    events = _parse_sse(r.text)
    kinds = [e["kind"] for e in events]
    assert kinds == [
        "plan",
        "attempt", "draft", "validate", "critique",
        "attempt", "revise", "validate", "critique",
        "save",
    ]
    final = events[-1]
    assert final["kind"] == "save"
    assert final["validation"]["ok"] is True
    assert final["markdown"].startswith("# Product")
    assert final["output_path"].endswith(".md")


def test_generate_endpoint_returns_degraded_event_when_budget_exhausted(client, tmp_path):
    class AlwaysInvalidModel:
        def invoke(self, messages):
            return _ai("# Product Requirements Document\n\n## Problem\nText.\n")

    app = create_app(chat_model_factory=lambda: AlwaysInvalidModel())
    c = TestClient(app)
    r = c.post("/api/generate", json={"idea": "valid length idea", "mode": "prd"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    final = events[-1]
    assert final["kind"] == "save"
    assert final["degraded"] is True
    assert final["validation"]["ok"] is False


def test_generate_endpoint_rejects_unknown_mode(client):
    r = client.post("/api/generate", json={"idea": "valid length idea", "mode": "memo"})
    assert r.status_code == 400


def test_history_endpoint_lists_saved_documents(client):
    """The fixture's FakeChatModel returns a complete PRD on revise, so PRD
    generations succeed and BRD generations fail validation. To test the
    history endpoint we monkey-patch the server's chat model factory for the
    duration of the test so both modes produce valid outputs."""

    class ModeAwareModel:
        """Routes by system message role: planner → brief, critic → JSON, writer → docs."""

        SECTIONS = {
            "prd": (
                "## Problem", "## Goals", "## Users", "## Requirements",
                "## Success Metrics", "## Risks and Assumptions",
            ),
            "brd": (
                "## Business Context", "## Objectives", "## Stakeholders",
                "## Scope", "## Business Rules", "## Risks and Dependencies",
            ),
            "tech_scope": (
                "## Technical Overview", "## Architecture", "## Data Model",
                "## Integrations", "## Delivery Plan", "## Risks and Open Questions",
            ),
        }

        def __init__(self):
            self._critic_replies = [json.dumps({"verdict": "pass", "criteria": [], "notes": "ok"})]
            self._drafts = {}

        def invoke(self, messages):
            system = messages[0].content if messages else ""
            all_text = "\n".join(m.content for m in messages if hasattr(m, "content"))
            if "planner" in system.lower():
                return _ai("Brief: keep it concrete.")
            if "critic" in system.lower():
                reply = self._critic_replies[0]
                return _ai(reply)
            # Writer: extract mode from prompt
            mode = None
            for candidate in self.SECTIONS:
                if candidate in all_text:
                    mode = candidate
                    break
            mode = mode or "prd"
            sections = self.SECTIONS[mode]
            body = "\n\n".join(f"{s}\nText." for s in sections)
            return _ai(f"# Document\n\n{body}\n")

    # Rebuild the app with the mode-aware model.
    from specguard import server as server_mod

    app = server_mod.create_app(chat_model_factory=lambda: ModeAwareModel())
    c = TestClient(app)
    with c.stream("POST", "/api/generate", json={"idea": "alpha idea", "mode": "prd"}) as r:
        assert r.status_code == 200
        for _ in r.iter_lines():
            pass
    with c.stream("POST", "/api/generate", json={"idea": "beta idea", "mode": "brd"}) as r:
        assert r.status_code == 200
        for _ in r.iter_lines():
            pass
    r = client.get("/api/history")
    assert r.status_code == 200
    docs = r.json()["documents"]
    assert len(docs) >= 2
    for d in docs:
        assert "path" in d
        assert "title" in d
        assert "mode" in d
        assert "created_at" in d
        assert "size_bytes" in d
        assert "valid" in d


def test_history_endpoint_returns_empty_when_no_outputs(client):
    r = client.get("/api/history")
    assert r.status_code == 200
    assert r.json()["documents"] == []


def test_document_endpoint_returns_markdown(client):
    gen = client.post("/api/generate", json={"idea": "read me later", "mode": "prd"})
    events = _parse_sse(gen.text)
    output_path = events[-1]["output_path"]

    r = client.get("/api/document", params={"path": output_path})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "# Product" in r.text


def _parse_sse(body: str) -> list[dict]:
    """Parse text/event-stream body into a list of {kind, ...} dicts."""
    events: list[dict] = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        data_lines = [
            line[len("data: "):]
            for line in chunk.splitlines()
            if line.startswith("data: ")
        ]
        if not data_lines:
            continue
        payload_str = "\n".join(data_lines)
        if payload_str == "[DONE]":
            continue
        payload = json.loads(payload_str)
        events.append(payload)
    return events
