"""System-prompt contract tests (pure stdlib — no API)."""
from app.brief_prompt import SECTIONS, SYSTEM_PROMPT, build_user_message


def test_all_six_sections_present_in_prompt():
    assert len(SECTIONS) == 6
    for heading in SECTIONS:
        assert f"## {heading}" in SYSTEM_PROMPT, f"missing section: {heading}"


def test_prompt_synthesizes_from_research_excerpts():
    assert "RESEARCH EXCERPTS" in SYSTEM_PROMPT


def test_prompt_forbids_speculation():
    assert "No speculation without a source" in SYSTEM_PROMPT


def test_user_message_includes_company_and_research():
    msg = build_user_message("Flexport", "[1] Flexport news\nURL: https://x.com\nText")
    assert "Flexport" in msg
    assert "https://x.com" in msg
    assert "RESEARCH EXCERPTS" in msg
