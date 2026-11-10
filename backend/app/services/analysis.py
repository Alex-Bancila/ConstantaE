"""Runs the three checks for a page and keeps the result (owner: David)."""

import uuid

from app.ai.rag import generate_report
from app.ai.vision import detect
from app.config import get_settings
from app.schemas import AnalysisResponse, AnalysisStatus, PageData
from app.services.trust import run_trust_checks
from app.workers import queue, store


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
    trust = run_trust_checks(page)
    failed_checks = [check for check in trust.checks if not check.passed]
    return AnalysisResponse(
        analysis_id=analysis_id,
        status=AnalysisStatus.DONE,
        images=[detect(url) for url in page.images],
        trust=trust,
        legal=generate_report(page, failed_checks),
    )


def get(analysis_id: str) -> AnalysisResponse | None:
    return store.load(analysis_id)
