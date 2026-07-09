from app.brief_prompt import build_sections


def test_default_sections_supply_chain_no_product():
    s = build_sections(focus="", has_product=False)
    assert s[0] == "Company Snapshot"
    assert "Financial Pulse & Trajectory" in s
    assert "Supply Chain & Ops Profile" in s
    assert s[-1] == "Sources"
    assert "Deal & Pricing" not in s


def test_focus_retitles_profile_section():
    s = build_sections(focus="marketing", has_product=False)
    assert "Marketing Profile" in s
    assert "Supply Chain & Ops Profile" not in s


def test_product_adds_deal_section_before_sources():
    s = build_sections(focus="", has_product=True)
    assert "Deal & Pricing" in s
    assert s.index("Deal & Pricing") == s.index("Sources") - 1
