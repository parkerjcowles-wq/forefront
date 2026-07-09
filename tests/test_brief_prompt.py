from app.brief_prompt import build_sections, build_system_prompt, build_user_message


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


def test_system_prompt_default_is_supply_chain():
    p = build_system_prompt(focus="", has_product=False)
    assert "Supply Chain & Ops Profile" in p
    assert "Financial Pulse & Trajectory" in p
    assert "Deal & Pricing" not in p            # no product -> no section
    assert "as of" in p.lower()                 # dated-financials rule present


def test_system_prompt_with_product_includes_deal_and_bands():
    p = build_system_prompt(focus="marketing", has_product=True)
    assert "Marketing Profile" in p
    assert "Deal & Pricing" in p
    assert "ACV" in p                           # deal-size cheat-sheet surfaced


def test_user_message_wraps_untrusted_fields():
    msg = build_user_message("Acme", "excerpt", focus="marketing",
                             call_context="renewal call", product="Widget", price="$40k")
    assert "Acme" in msg and "excerpt" in msg
    assert "marketing" in msg and "renewal call" in msg
    assert "Widget" in msg and "$40k" in msg
    # Untrusted data must be labeled as data, not instructions.
    assert "USER-SUPPLIED" in msg or "untrusted" in msg.lower()


def test_user_message_omits_blank_optional_fields():
    msg = build_user_message("Acme", "excerpt")
    assert "Sales focus" not in msg
    assert "Call context" not in msg
    assert "Product being pitched" not in msg
    assert "Price / model" not in msg
    assert "Acme" in msg
