from specguard.tools.domain_checklist import get_checklist

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
