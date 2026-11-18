"""Runs the three checks for a page and keeps the result (owner: David).

With AI_MODE=real the image detector and the legal report depend on models, Postgres
and the Claude API, so each part runs on its own: if one fails, the error is logged
and that part is replaced by a fallback, while the other parts are still returned.
The images and the legal report run in parallel, and every run logs how long each
part took (see docs/real-mode-timing.md).
"""

import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app import db
from app.ai.rag import generate_report
from app.ai.vision.detector import FAILURE_SIGNALS
from app.config import get_settings
from app.schemas import (
    AnalysisResponse,
    AnalysisStatus,
    ImageResult,
    LegalReport,
    PageData,
    TrustCheck,
    TrustReport,
)
from app.services.trust import run_trust_checks
from app.workers import cache, queue, store

logger = logging.getLogger(__name__)

# Signal of an image whose check crashed (as opposed to one the detector could not
# download or decode, which the detector reports itself).
IMAGE_FAILED_SIGNAL = "Image analysis failed"


@dataclass(frozen=True)
class StageTimings:
    """How long each part of one analysis took, in milliseconds."""

    trust_ms: float
    images_ms: float
    legal_ms: float
    total_ms: float

    def __str__(self) -> str:
        return (
            f"trust={self.trust_ms:.0f}ms images={self.images_ms:.0f}ms "
            f"legal={self.legal_ms:.0f}ms total={self.total_ms:.0f}ms"
        )


def start(page: PageData) -> AnalysisResponse:
    analysis_id = uuid.uuid4().hex
    if get_settings().async_jobs:
        pending = AnalysisResponse(analysis_id=analysis_id, status=AnalysisStatus.PENDING)
        store.save(pending)
        queue.enqueue(analysis_id, page)
        return pending

    result = run(analysis_id, page)
    store.save(result)
    return result


def run(analysis_id: str, page: PageData) -> AnalysisResponse:
    result, _ = run_timed(analysis_id, page)
    return result


def run_timed(analysis_id: str, page: PageData) -> tuple[AnalysisResponse, StageTimings]:
    """Run the three checks and also return how long each one took."""
    started = time.perf_counter()

    trust, trust_ms = _timed(lambda: _safe_trust(page))
    failed_checks = [check for check in trust.checks if not check.passed] if trust else []

    # The images (download + model) and the legal report (search + LLM) don't depend
    # on each other, so the analysis takes as long as the slower of the two. The
    # images stay sequential within their thread: the vision model loads lazily and
    # CPU inference doesn't get faster by running several images at once.
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis") as pool:
        images_future = pool.submit(_timed, lambda: [_safe_image(url) for url in page.images])
        legal_future = pool.submit(_timed, lambda: _safe_legal(page, failed_checks))
        images, images_ms = images_future.result()
        legal, legal_ms = legal_future.result()

    timings = StageTimings(
        trust_ms=trust_ms,
        images_ms=images_ms,
        legal_ms=legal_ms,
        total_ms=_elapsed_ms(started),
    )
    logger.info(
        "analysis %s (%s, %d images): %s",
        analysis_id,
        get_settings().ai_mode,
        len(page.images),
        timings,
    )
    result = AnalysisResponse(
        analysis_id=analysis_id,
        status=AnalysisStatus.DONE,
        images=images,
        trust=trust,
        legal=legal,
    )
    db.record(result, page)
    return result, timings


def is_failed_image(result: ImageResult) -> bool:
    """True if the image could not be scored, so its result must not be cached."""
    return any(
        signal.startswith(prefix)
        for signal in result.signals
        for prefix in (*FAILURE_SIGNALS, IMAGE_FAILED_SIGNAL)
    )


def _safe_trust(page: PageData) -> TrustReport | None:
    try:
        return run_trust_checks(page)
    except Exception:
        logger.exception("Trust checks failed for %s", page.url)
        return None


def _safe_image(url: str) -> ImageResult:
    try:
        return cache.detect_with_cache(url, should_cache=lambda result: not is_failed_image(result))
    except Exception as exc:
        # One broken image (or model) must not hide the other images and checks.
        # The details stay in the log; the user only sees that this image failed.
        logger.exception("Image analysis failed for %s", url)
        return ImageResult(
            url=url,
            ai_probability=0.0,
            signals=[f"{IMAGE_FAILED_SIGNAL}: {type(exc).__name__}"],
        )


def _safe_legal(page: PageData, failed_checks: list[TrustCheck]) -> LegalReport | None:
    try:
        return generate_report(page, failed_checks)
    except Exception:
        # e.g. Postgres down or the laws not ingested. The popup shows "no legal report".
        logger.exception("Legal report failed for %s", page.url)
        return None


def _timed[T](work: Callable[[], T]) -> tuple[T, float]:
    started = time.perf_counter()
    return work(), _elapsed_ms(started)


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def get(analysis_id: str) -> AnalysisResponse | None:
    result = store.load(analysis_id)
    if result is None:
        return None

    if result.status == AnalysisStatus.PENDING and get_settings().async_jobs:
        job = queue.get_job(analysis_id)
        if job and job.is_failed:
            failed = AnalysisResponse(analysis_id=analysis_id, status=AnalysisStatus.FAILED)
            store.save(failed)
            return failed

    return result
