import pytest
from fastapi.testclient import TestClient

from app import cache
from app.main import app


@pytest.fixture(autouse=True)
def _reset():
    cache.reset()
    yield
    cache.reset()


@pytest.fixture
def client():
    return TestClient(app)


def test_security_headers_present(client):
    r = client.get("/api/showcase/project44")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in r.headers
    assert "referrer-policy" in r.headers


def test_docs_endpoints_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


from app.config import RATE_LIMIT_MAX


def test_per_ip_rate_limit_returns_429(client, monkeypatch):
    from app import cache, main
    # Raise the session cap out of the way so ONLY the IP limiter can 429.
    monkeypatch.setattr(cache, "MAX_CUSTOM_BRIEFS", 10_000)
    monkeypatch.setattr(
        main, "generate_brief",
        lambda company, **kw: {"markdown": "## Company Snapshot\nx",
                               "sources": ["https://e.com"]},
    )
    last = None
    for i in range(RATE_LIMIT_MAX + 2):
        last = client.post("/api/brief", json={"company": f"Co {i}"})
    assert last.status_code == 429
    assert last.json().get("rate_limited") is True
    assert "limit_reached" not in last.json()   # proves the IP guard tripped, not the session cap


def test_ip_rate_limiter_trips_after_max():
    from app import cache
    cache.reset()
    ip = "203.0.113.7"
    for _ in range(RATE_LIMIT_MAX):
        assert cache.ip_rate_limited(ip) is False
    assert cache.ip_rate_limited(ip) is True   # the (MAX+1)th call trips it
    cache.reset()
