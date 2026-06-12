import pytest
from specguard.rubrics import get_rubric, list_modes, ModeError

def test_list_modes_includes_prd_brd_tech():
    assert set(list_modes()) == {"prd", "brd", "tech_scope"}

def test_prd_rubric_contains_core_items():
    r = get_rubric("prd").lower()
    for needle in ("user persona", "mvp", "acceptance criteria", "risks", "open questions"):
        assert needle in r, f"missing: {needle}"

def test_brd_rubric_mentions_stakeholders():
    r = get_rubric("brd").lower()
    assert "stakeholder" in r

def test_tech_scope_rubric_mentions_api_and_data_model():
    r = get_rubric("tech_scope").lower()
    assert "api" in r
    assert "data" in r

def test_unknown_mode_raises():
    with pytest.raises(ModeError):
        get_rubric("nonsense")
