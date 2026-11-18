import json

import fakeredis
import pytest
from fastapi.testclient import TestClient
from rq.worker import SimpleWorker

from app.config import REPO_ROOT, get_settings
from app.main import app


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("AI_MODE", "mock")
    monkeypatch.setenv("ASYNC", "false")
    monkeypatch.setenv("DATABASE_URL", "")  # tests never need Postgres, even if .env sets it
    monkeypatch.setenv("ANAF_CHECK", "false")  # tests never call the real ANAF API
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
    monkeypatch.setattr("app.services.anaf.get_redis_connection", lambda: conn)
    # On Linux the default RQ Worker runs each job in a forked child process, which
    # writes to its own copy of the in-memory fake Redis. SimpleWorker runs jobs in
    # this process, so the tests see the results on every platform.
    monkeypatch.setattr("app.workers.worker.get_worker_class", lambda: SimpleWorker)
    yield conn


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def example_page() -> dict:
    return json.loads((REPO_ROOT / "shared" / "example-page.json").read_text(encoding="utf-8"))
