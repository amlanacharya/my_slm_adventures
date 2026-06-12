from specguard.prompts.system import build_system_prompt

def test_prompt_is_senior_pm():
    p = build_system_prompt("prd").lower()
    assert "product manager" in p
    assert "avoid" in p and "vague" in p

def test_prompt_lists_required_sections():
    p = build_system_prompt("prd").lower()
    for sec in ("product summary", "target users", "core workflows",
                "functional requirements", "data model",
                "acceptance criteria", "risks", "mvp", "open questions"):
        assert sec in p, f"missing section: {sec}"

def test_brd_prompt_mentions_stakeholders():
    p = build_system_prompt("brd").lower()
    assert "stakeholder" in p

def test_tech_scope_prompt_mentions_api_and_data_model():
    p = build_system_prompt("tech_scope").lower()
    assert "api" in p and "data model" in p
