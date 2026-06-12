from specguard.tools.clarifier import get_clarifying_questions
from specguard.tools.domain_checklist import get_checklist
from specguard.tools.scope_estimator import estimate_scope


def test_get_checklist_interior_designer_includes_quotation():
    items = get_checklist("interior designer")
    joined = " ".join(items).lower()
    assert "quotation" in joined
    assert "gst" in joined or "tax" in joined


def test_get_checklist_unknown_domain_returns_generic():
    items = get_checklist("underwater basket weaving consortium")
    assert len(items) >= 5
    assert all(isinstance(i, str) and i for i in items)


def test_get_checklist_fintech_includes_kyc():
    items = get_checklist("fintech nbfc lending")
    joined = " ".join(items).lower()
    assert "kyc" in joined or "compliance" in joined


def test_estimate_scope_returns_required_keys():
    est = estimate_scope("interior designer billing app")
    for k in ("size", "team", "weeks", "risks"):
        assert k in est


def test_estimate_scope_fintech_is_medium_or_large():
    est = estimate_scope("nbfc lending platform with kyc and emi")
    assert est["size"] in ("medium", "large")
    assert est["weeks"] >= 8


def test_estimate_scope_unknown_is_small_or_medium():
    est = estimate_scope("todo list for cats")
    assert est["size"] in ("small", "medium")


def test_clarifier_returns_questions():
    qs = get_clarifying_questions("Build an app for interior designers to manage billing.")
    assert len(qs) >= 5
    assert all(q.endswith("?") for q in qs)


def test_clarifier_handles_empty_idea():
    qs = get_clarifying_questions("")
    assert len(qs) >= 3
