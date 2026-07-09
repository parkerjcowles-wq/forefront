"""FastAPI endpoint tests — generate_brief mocked, cache reset per test."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import cache, main
from app.config import MAX_CUSTOM_BRIEFS
from app.main import SHOWCASE_DIR, app


@pytest.fixture(autouse=True)
def _reset():
    cache.reset()
    yield
    cache.reset()


@pytest.fixture
def client():
    return TestClient(app)


def _fake_brief(*, sources=None):
    calls = {"n": 0, "last": None}

    def _gen(company, **kwargs):
        calls["n"] += 1
        calls["last"] = kwargs
        return {"markdown": f"## Company Snapshot\nBrief for {company}.",
                "sources": sources or ["https://example.com/src"]}

    return _gen, calls


# --- showcase ---------------------------------------------------------------

def test_showcase_unknown_slug_404(client):
    assert client.get("/api/showcase/not-a-company").status_code == 404


def test_showcase_known_slug_returns_markdown(client):
    # Self-sufficient: ensure a showcase file exists for the test.
    path = SHOWCASE_DIR / "project44.md"
    if not path.exists():
        SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text("## Company Snapshot\nproject44 placeholder.", encoding="utf-8")
    r = client.get("/api/showcase/project44")
    assert r.status_code == 200
    body = r.json()
    assert body["company"] == "project44"
    assert body["markdown"].strip()
    assert body["showcase"] is True


# --- live brief -------------------------------------------------------------

def test_brief_happy_path(client, monkeypatch):
    gen, _ = _fake_brief()
    monkeypatch.setattr(main, "generate_brief", gen)
    r = client.post("/api/brief", json={"company": "Flexport"})
    assert r.status_code == 200
    body = r.json()
    assert body["company"] == "Flexport"
    assert "Brief for Flexport" in body["markdown"]
    assert body["cached"] is False
    assert main.SESSION_COOKIE in r.cookies


def test_brief_invalid_company_400(client, monkeypatch):
    gen, _ = _fake_brief()
    monkeypatch.setattr(main, "generate_brief", gen)
    r = client.post("/api/brief", json={"company": "   "})
    assert r.status_code == 400


def test_brief_cached_second_call_does_not_regenerate(client, monkeypatch):
    gen, calls = _fake_brief()
    monkeypatch.setattr(main, "generate_brief", gen)
    first = client.post("/api/brief", json={"company": "Kinaxis"})
    second = client.post("/api/brief", json={"company": "kinaxis"})  # same key, diff case
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert calls["n"] == 1  # generate_brief called only once


def test_brief_session_cap_returns_429(client, monkeypatch):
    gen, _ = _fake_brief()
    monkeypatch.setattr(main, "generate_brief", gen)
    # Distinct companies to bypass the cache and burn the session allowance.
    for i in range(MAX_CUSTOM_BRIEFS):
        ok = client.post("/api/brief", json={"company": f"Company {i}"})
        assert ok.status_code == 200
    blocked = client.post("/api/brief", json={"company": "One Too Many"})
    assert blocked.status_code == 429
    assert blocked.json()["limit_reached"] is True


def test_brief_generation_error_returns_502(client, monkeypatch):
    from app.research import BriefGenerationError

    def boom(company, **kwargs):
        raise BriefGenerationError("research service down")

    monkeypatch.setattr(main, "generate_brief", boom)
    r = client.post("/api/brief", json={"company": "Honeywell"})
    assert r.status_code == 502
    assert "research service down" in r.json()["error"]


def test_brief_accepts_optional_fields(client, monkeypatch):
    gen, calls = _fake_brief()
    monkeypatch.setattr(main, "generate_brief", gen)
    r = client.post("/api/brief", json={
        "company": "Acme", "focus": "marketing",
        "call_context": "renewal call", "product": "Widget", "price": "$40k",
    })
    assert r.status_code == 200
    assert calls["last"]["focus"] == "marketing"
    assert calls["last"]["product"] == "Widget"


def test_brief_focus_changes_cache_key(client, monkeypatch):
    gen, calls = _fake_brief()
    monkeypatch.setattr(main, "generate_brief", gen)
    client.post("/api/brief", json={"company": "Acme"})
    client.post("/api/brief", json={"company": "Acme", "focus": "marketing"})
    assert calls["n"] == 2  # different focus -> not a cache hit
