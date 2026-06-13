from __future__ import annotations

import json

from langchain_core.messages import AIMessage

from specguard.roles.critic import CriticVerdict, critique, extract_json


GOOD_JSON = json.dumps(
    {
        "verdict": "needs_revision",
        "criteria": [{"id": "prd-1", "score": 1, "reason": "objective is vague"}],
        "notes": "Tighten the objective.",
    }
)


def test_extract_json_plain():
    assert extract_json(GOOD_JSON)["verdict"] == "needs_revision"


def test_extract_json_fenced():
    fenced = f"```json\n{GOOD_JSON}\n```"
    assert extract_json(fenced)["notes"] == "Tighten the objective."


def test_extract_json_with_prose_prefix():
    text = f"Here is my evaluation:\n{GOOD_JSON}\nHope that helps!"
    assert extract_json(text)["criteria"][0]["id"] == "prd-1"


def test_extract_json_multiline():
    """re.DOTALL must be set or multi-line JSON objects fail to extract."""
    multiline = json.dumps({"verdict": "pass", "criteria": [], "notes": "line1\nline2"})
    text = f"Analysis:\n{multiline}\nend"
    result = extract_json(text)
    assert result is not None
    assert "line1" in result["notes"]


def test_extract_json_garbage_returns_none():
    assert extract_json("I think the document is fine overall.") is None


class JsonModel:
    def invoke(self, messages):
        return AIMessage(content=GOOD_JSON)


class GarbageModel:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(content="not json at all")


class FakeValidator:
    def __init__(self, ok: bool, missing: tuple[str, ...] = ()):
        self._ok = ok
        self._missing = missing

    def __call__(self, text: str, sections: tuple[str, ...]):
        class Result:
            ok = True
            missing_sections = ()
        class FakeResult:
            ok = False
            missing_sections = ("## Users",)
        return FakeResult() if self._ok is False else Result()


def test_critique_parses_verdict():
    verdict = critique(JsonModel(), mode="prd", draft="## Problem\nText.", validator=FakeValidator(True))
    assert isinstance(verdict, CriticVerdict)
    assert verdict.passed is False
    assert verdict.fallback is False
    assert verdict.criteria[0].id == "prd-1"
    assert verdict.criteria[0].score == 1
    assert "Tighten" in verdict.notes


def test_critique_retries_once_then_falls_back():
    model = GarbageModel()
    verdict = critique(model, mode="prd", draft="## Problem\nText.", validator=FakeValidator(True))
    assert model.calls == 2  # initial + one retry
    assert verdict.fallback is True
    assert verdict.passed is True  # fallback never blocks; validators gate alone
    assert verdict.criteria == ()


def test_critique_validator_not_called_on_model_success():
    """Validator is only called to build the fallback verdict, not to gate the model path."""
    validator = FakeValidator(False)
    verdict = critique(JsonModel(), mode="prd", draft="## Problem\nText.", validator=validator)
    assert verdict.passed is False
    assert verdict.fallback is False
