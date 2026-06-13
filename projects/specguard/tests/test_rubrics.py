import pytest

from specguard.rubrics import ModeError, RubricCriterion, get_rubric, get_rubric_criteria, list_modes

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


def test_prd_rubric_criteria_parses_numbered_checklist_items():
    criteria = get_rubric_criteria("prd")

    assert criteria == (
        RubricCriterion("prd-1", "Clear product objective (one sentence)."),
        RubricCriterion("prd-2", "Clear primary user persona with job-to-be-done."),
        RubricCriterion("prd-3", "MVP scope is explicitly separated from Phase 2."),
        RubricCriterion("prd-4", "At least 5 functional requirements, each testable."),
        RubricCriterion("prd-5", "At least 5 acceptance criteria in Given/When/Then form."),
        RubricCriterion("prd-6", "Data entities are listed with key fields."),
        RubricCriterion("prd-7", "Risks AND assumptions are both included."),
        RubricCriterion("prd-8", "Output is practical and specific — no vague AI/launch language."),
        RubricCriterion("prd-9", "Open questions for stakeholders are included."),
        RubricCriterion("prd-10", "Final answer is structured with the requested sections."),
    )


def test_get_rubric_criteria_unknown_mode_raises():
    with pytest.raises(ModeError):
        get_rubric_criteria("nonsense")


def test_unknown_mode_raises():
    with pytest.raises(ModeError):
        get_rubric("nonsense")
