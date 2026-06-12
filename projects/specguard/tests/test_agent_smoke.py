import os
import pytest
from specguard.agent import build_agent, SUPPORTED_MODES

# Skip these tests if deepagents isn't importable in the test env
deepagents = pytest.importorskip("deepagents")
RubricMiddleware = pytest.importorskip("deepagents").RubricMiddleware
InMemorySaver = pytest.importorskip("langgraph.checkpoint.memory").InMemorySaver

def test_supported_modes():
    assert set(SUPPORTED_MODES) == {"prd", "brd", "tech_scope"}

def test_build_agent_returns_compiled_graph():
    os.environ.setdefault("OPENAI_API_KEY", "sk-tes...lder")
    agent = build_agent("prd")
    # A compiled state graph exposes .invoke and .get_state
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "get_state")

def test_build_agent_unknown_mode_raises():
    with pytest.raises(ValueError):
        build_agent("nonsense")
