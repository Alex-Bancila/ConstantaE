import json

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


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def example_page() -> dict:
    return json.loads((REPO_ROOT / "shared" / "example-page.json").read_text(encoding="utf-8"))
