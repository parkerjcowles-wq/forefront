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
