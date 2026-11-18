"""Measures how long one analysis takes with AI_MODE=real (owner: David).

Usage (from backend/, with requirements-vision.txt installed, the laws ingested and
LLM_API_KEY set in .env):

    python scripts/measure_analysis.py legitimate-shop
    python scripts/measure_analysis.py suspicious-seller --runs 5
    python scripts/measure_analysis.py sample

Reads the page data from qa/pages/<page>/expected.json (or the starter sample page),
serves qa/pages on a local HTTP port if --base is not given, and runs the analysis once
cold, while the models still have to load, then --runs times warm. Every run starts with
an empty in-memory image cache, so the images are downloaded and scored each time and
Redis does not need to run. Prints a Markdown table for docs/real-mode-timing.md and
checks that every part really ran (no failed images, a legal report, no mock data).
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import statistics
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin

import fakeredis

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import REPO_ROOT, get_settings  # noqa: E402
from app.schemas import AnalysisResponse, PageData  # noqa: E402
from app.services import analysis  # noqa: E402
from app.workers import cache  # noqa: E402

PAGES_DIR = REPO_ROOT / "qa" / "pages"
# Above this, waiting on POST /analyze without ASYNC feels broken.
SYNC_LIMIT_SECONDS = 8
# The popup polls an ASYNC analysis for at most this long (extension/entrypoints/popup/App.tsx).
POLL_LIMIT_SECONDS = 60

SAMPLE_PAGE_DATA: dict[str, object] = {
    "title": "iPhone 15 Pro, sigilat",
    "price": 1200,
    "currency": "RON",
    "images": ["photo1.png", "photo2.png"],
    "seller": {"name": None, "cui": None},
    "legalLinks": {"anpc": False, "sol": True},
    "hasReturnPolicy": False,
}


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def resolve_base_url(page_name: str, base_url: str | None) -> Iterator[str]:
    if base_url:
        yield base_url if base_url.endswith("/") else f"{base_url}/"
        return
    handler = functools.partial(_QuietHandler, directory=str(PAGES_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/{page_name}/"
    finally:
        server.shutdown()
        server.server_close()


def load_page(name: str, base_url: str) -> PageData:
    expected_path = PAGES_DIR / name / "expected.json"
    if expected_path.exists():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        data = dict(expected["pageData"])
    elif name == "sample":
        data = dict(SAMPLE_PAGE_DATA)
    else:
        raise FileNotFoundError(f"No expected.json found in {PAGES_DIR / name}")
    data["images"] = [urljoin(base_url, image) for image in data.get("images", [])]
    data.setdefault("url", urljoin(base_url, "product.html"))
    return PageData.model_validate(data)


def find_problems(result: AnalysisResponse) -> list[str]:
    problems = [
        f"image {image.url}: {image.signals[0]}"
        for image in result.images
        if analysis.is_failed_image(image)
    ]
    if result.trust is None:
        problems.append("trust checks failed (see the log above)")
    if result.legal is None:
        problems.append("legal report failed (see the log above)")
    signals = [signal for image in result.images for signal in image.signals]
    if any("[MOCK]" in text for text in [*signals, result.legal.summary if result.legal else ""]):
        problems.append("mock data in the result: is AI_MODE=real?")
    return problems


def print_result(result: AnalysisResponse) -> None:
    print("\nResult of the last run:")
    for image in result.images:
        print(f"- {image.url}: AI {image.ai_probability:.0%} ({'; '.join(image.signals)})")
    if result.trust:
        print(f"- trust score: {result.trust.score}")
    if result.legal:
        summary = result.legal.summary
        print(f"- legal: {len(result.legal.citations)} citations. {summary[:160]}")


def recommend(cold_seconds: float, warm_seconds: float) -> str:
    if cold_seconds > POLL_LIMIT_SECONDS:
        return (
            f"cold run over {POLL_LIMIT_SECONDS} s: warm the models up before the demo "
            "(analyse a page once after starting the backend)."
        )
    if warm_seconds > SYNC_LIMIT_SECONDS:
        return f"warm median over {SYNC_LIMIT_SECONDS} s: use ASYNC=true for the demo."
    return f"warm median within {SYNC_LIMIT_SECONDS} s: ASYNC=false is fine for the demo."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("page", help="folder name in qa/pages, e.g. legitimate-shop")
    parser.add_argument("--base", help="URL the page is served at (default: built-in local server)")
    parser.add_argument("--runs", type=int, default=3, help="warm runs after the cold one")
    parser.add_argument("--mode", choices=["real", "mock"], default="real")
    args = parser.parse_args()

    os.environ["AI_MODE"] = args.mode
    get_settings.cache_clear()

    image_cache = fakeredis.FakeRedis()
    cache.get_redis_connection = lambda: image_cache

    with resolve_base_url(args.page, args.base) as base_url:
        page = load_page(args.page, base_url)

        print(f"Page {args.page}: {len(page.images)} images, AI_MODE={args.mode}\n")
        print("| Run | Trust | Images | Legal | Total |")
        print("|---|---|---|---|---|")
        totals = []
        result = None
        for run in range(args.runs + 1):
            image_cache.flushall()
            result, timings = analysis.run_timed(f"measure-{run}", page)
            totals.append(timings.total_ms / 1000)
            label = "cold" if run == 0 else f"warm {run}"
            print(
                f"| {label} | {timings.trust_ms:.0f} ms | {timings.images_ms / 1000:.2f} s "
                f"| {timings.legal_ms / 1000:.2f} s | **{timings.total_ms / 1000:.2f} s** |"
            )

    warm = statistics.median(totals[1:]) if len(totals) > 1 else totals[0]
    print(f"\nCold {totals[0]:.2f} s, warm median {warm:.2f} s: {recommend(totals[0], warm)}")

    assert result is not None
    print_result(result)
    problems = find_problems(result) if args.mode == "real" else []
    for problem in problems:
        print(f"PROBLEM: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
