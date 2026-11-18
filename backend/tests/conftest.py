import json

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, get_settings
from app.main import app


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("AI_MODE", "mock")
    monkeypatch.setenv("ASYNC", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    server = fakeredis.FakeServer()
    conn = fakeredis.FakeRedis(server=server)
    monkeypatch.setattr("app.workers.store.get_redis_connection", lambda: conn)
    monkeypatch.setattr("app.workers.queue.get_redis_connection", lambda: conn)
    monkeypatch.setattr("app.workers.cache.get_redis_connection", lambda: conn)
    yield conn


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def example_page() -> dict:
    return json.loads((REPO_ROOT / "shared" / "example-page.json").read_text(encoding="utf-8"))
