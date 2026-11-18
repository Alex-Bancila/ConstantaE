"""AI_MODE=real end to end on a demo page (issue #15). Skipped unless REAL_AI_E2E=1.

Needs requirements-vision.txt, DATABASE_URL with the laws ingested
(python -m app.ai.rag.ingest) and LLM_API_KEY, in the environment or backend/.env:

    REAL_AI_E2E=1 pytest tests/test_real_e2e.py -s

The demo page is served by a local HTTP server started by the test; the image cache
uses the in-memory Redis from conftest.py.
"""

import functools
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.config import REPO_ROOT, get_settings
from app.schemas import PageData
from app.services import analysis

pytestmark = pytest.mark.skipif(
    os.environ.get("REAL_AI_E2E") != "1", reason="set REAL_AI_E2E=1 to run the real AI models"
)

PAGES_DIR = REPO_ROOT / "qa" / "pages"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture
def pages_url():
    handler = functools.partial(_QuietHandler, directory=str(PAGES_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize("page_name", ["legitimate-shop", "suspicious-seller"])
def test_real_mode_end_to_end_on_demo_page(monkeypatch, pages_url, page_name):
    monkeypatch.setenv("AI_MODE", "real")
    get_settings.cache_clear()
    expected = json.loads((PAGES_DIR / page_name / "expected.json").read_text(encoding="utf-8"))
    data = dict(expected["pageData"])
    data["url"] = f"{pages_url}/{page_name}/product.html"
    data["images"] = [f"{pages_url}/{page_name}/{image}" for image in data["images"]]

    result, timings = analysis.run_timed("real-e2e", PageData.model_validate(data))
    print(f"\n{page_name}: {timings}")

    assert result.status == "done"
    assert len(result.images) == len(data["images"])
    for image in result.images:
        assert not analysis.is_failed_image(image), image.signals
        assert any(signal.startswith("Model score") for signal in image.signals)
    assert result.trust is not None
    assert result.legal is not None
    assert "[MOCK]" not in result.legal.summary
