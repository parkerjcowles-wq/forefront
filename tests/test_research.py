"""research.py tests — Exa searcher + Groq client fully mocked, no live API."""
from types import SimpleNamespace

import pytest

from app.research import BriefGenerationError, generate_brief


def _groq_response(text):
    """Mimic groq client.chat.completions.create(...) return shape."""
    msg = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


class FakeGroq:
    def __init__(self, text=None, raise_exc=None):
        self._text = text
        self._raise = raise_exc
        self.calls = 0
        self.last_messages = None
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls += 1
        self.last_messages = kwargs.get("messages")
        if self._raise:
            raise self._raise
        return _groq_response(self._text)


def _searcher(results):
    return lambda company: list(results)


SAMPLE_RESULTS = [
    {"title": "Flexport overview", "url": "https://flexport.com/about", "text": "Digital freight forwarder."},
    {"title": "Flexport news", "url": "https://news.example.com/flexport", "text": "Layoffs in 2023."},
]


def test_happy_path_returns_markdown_and_sources():
    md = "## Company Snapshot\nFlexport. https://flexport.com/about"
    groq = FakeGroq(text=md)
    result = generate_brief("Flexport", groq_client=groq, searcher=_searcher(SAMPLE_RESULTS))
    assert result["markdown"] == md
    assert "https://flexport.com/about" in result["sources"]
    assert groq.calls == 1


def test_research_excerpts_are_passed_into_the_prompt():
    groq = FakeGroq(text="## Company Snapshot\nok")
    generate_brief("Flexport", groq_client=groq, searcher=_searcher(SAMPLE_RESULTS))
    user_turn = groq.last_messages[1]["content"]
    assert "https://news.example.com/flexport" in user_turn
    assert "Layoffs in 2023." in user_turn


def test_no_search_results_raises():
    groq = FakeGroq(text="should not be called")
    with pytest.raises(BriefGenerationError):
        generate_brief("Nowhere Inc", groq_client=groq, searcher=_searcher([]))
    assert groq.calls == 0  # never reaches synthesis


def test_search_failure_is_wrapped():
    def boom(company):
        raise RuntimeError("exa down")

    with pytest.raises(BriefGenerationError):
        generate_brief("Acme", groq_client=FakeGroq(text="x"), searcher=boom)


def test_groq_error_is_wrapped():
    groq = FakeGroq(raise_exc=RuntimeError("503 overloaded"))
    with pytest.raises(BriefGenerationError):
        generate_brief("Acme", groq_client=groq, searcher=_searcher(SAMPLE_RESULTS))


def test_empty_completion_raises():
    groq = FakeGroq(text="")
    with pytest.raises(BriefGenerationError):
        generate_brief("Acme", groq_client=groq, searcher=_searcher(SAMPLE_RESULTS))


def test_sources_fall_back_to_results_when_brief_omits_urls():
    groq = FakeGroq(text="## Company Snapshot\nNo URLs cited in body.")
    result = generate_brief("Flexport", groq_client=groq, searcher=_searcher(SAMPLE_RESULTS))
    # Brief cited none, so sources fall back to the result URLs.
    assert result["sources"] == [
        "https://flexport.com/about",
        "https://news.example.com/flexport",
    ]


from app import research


def test_generate_brief_passes_focus_and_product_into_prompt():
    groq = FakeGroq(text="## Company Snapshot\nok")
    generate_brief(
        "Acme", focus="marketing", call_context="renewal", product="Widget",
        price="$40k", groq_client=groq, searcher=_searcher(SAMPLE_RESULTS),
    )
    system_turn = groq.last_messages[0]["content"]
    user_turn = groq.last_messages[1]["content"]
    assert "Marketing Profile" in system_turn      # dynamic section title
    assert "Deal & Pricing" in system_turn          # product -> deal section
    assert "Widget" in user_turn and "renewal" in user_turn


def test_exa_search_is_focus_aware_and_concurrent(monkeypatch):
    seen_queries = []

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"title": "t", "url": "https://ex.com/a",
                                 "text": "body", "publishedDate": "2026-01-01"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen_queries.append(json["query"])
        assert "startPublishedDate" in json  # recency filter applied
        return FakeResp()

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(research.requests, "post", fake_post)
    out = research.exa_search("Acme", focus="marketing")
    joined = " ".join(seen_queries)
    assert "marketing" in joined          # focus queries used
    assert "earnings" in joined or "revenue" in joined  # finance queries included
    assert out and out[0]["published"] == "2026-01-01"


def test_parse_sources_drops_individual_linkedin_profiles():
    from app.research import _parse_sources
    md = ("See https://example.com/a and "
          "https://www.linkedin.com/in/jane-doe and "
          "https://www.linkedin.com/search/results/people/?keywords=Acme%20CEO")
    out = _parse_sources(md, [])
    assert "https://example.com/a" in out
    assert not any("/in/" in u for u in out)                 # profile filtered out
    assert any("search/results/people" in u for u in out)    # search link kept


def test_run_query_retries_without_recency_when_filtered_empty(monkeypatch):
    calls = []

    class R:
        def __init__(self, data):
            self._d = data
        def raise_for_status(self):
            pass
        def json(self):
            return {"results": self._d}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        if "startPublishedDate" in json:
            return R([])  # recency-filtered pass finds nothing
        return R([{"title": "t", "url": "https://ex.com/a", "text": "x", "publishedDate": ""}])

    monkeypatch.setattr(research.requests, "post", fake_post)
    res = research._run_query("q", "key", "2025-01-01")
    assert len(calls) == 2  # filtered attempt, then unfiltered retry
    assert res and res[0]["url"] == "https://ex.com/a"
