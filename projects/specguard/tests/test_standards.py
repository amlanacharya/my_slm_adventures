from specguard.standards import REQUIRED_SECTIONS, load_standard


def test_load_standard_returns_markdown_for_each_mode():
    for mode in ("prd", "brd", "tech_scope"):
        standard = load_standard(mode)
        assert standard.startswith("# ")
        assert len(standard) > 200


def test_required_sections_are_defined_for_each_mode():
    assert set(REQUIRED_SECTIONS) == {"prd", "brd", "tech_scope"}
    for sections in REQUIRED_SECTIONS.values():
        assert len(sections) >= 5
        assert all(section.startswith("## ") for section in sections)


def test_load_standard_rejects_unknown_mode():
    try:
        load_standard("memo")
    except ValueError as exc:
        assert "unknown mode" in str(exc)
    else:
        raise AssertionError("expected ValueError")
