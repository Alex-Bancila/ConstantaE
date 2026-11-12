"""Background job queue for the slow AI work (owner: Marius).

Redis-backed queue using RQ.
"""

import logging
from typing import Any

from redis import Redis
from rq import Queue
from rq.job import Job

from app.config import get_settings
from app.schemas import PageData

logger = logging.getLogger(__name__)


def create_redis_connection(url: str | None = None) -> Redis:
    """Creates a raw Redis client from an explicit URL or REDIS_URL setting."""
    settings = get_settings()
    redis_url = url or settings.redis_url or "redis://localhost:6379"
    return Redis.from_url(redis_url)


def get_redis_connection() -> Redis:
    """Creates a Redis client from the REDIS_URL setting."""
    return create_redis_connection()


def get_queue(name: str = "default", connection: Redis | None = None) -> Queue:
    """Returns an RQ Queue connected to Redis."""
    conn = connection or get_redis_connection()
    return Queue(name, connection=conn)


def get_job(job_id: str, connection: Redis | None = None) -> Job | None:
    """Fetches an existing RQ Job by ID, or None if not found."""
    from rq.exceptions import NoSuchJobError

    conn = connection or get_redis_connection()
    try:
        return Job.fetch(job_id, connection=conn)
    except NoSuchJobError:
        return None


def run_test_job(message: str = "ping") -> str:
    """A lightweight test job to verify worker execution end-to-end."""
    return f"pong: {message}"


def run_analysis_job(analysis_id: str, page_data: dict[str, Any] | PageData) -> dict[str, Any]:
    """Processes a page analysis job and stores the completed result.

    If an error occurs, saves a failed response so it never gets stuck in pending.
    """
    from app.schemas import AnalysisResponse, AnalysisStatus
    from app.services.analysis import run
    from app.workers import store

    try:
        if isinstance(page_data, dict):
            page = PageData.model_validate(page_data)
        else:
            page = page_data

        result = run(analysis_id, page)
        store.save(result)
        return result.model_dump(mode="json", by_alias=True)
    except Exception as exc:
        logger.exception("Analysis job %s failed: %s", analysis_id, exc)
        failed_response = AnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.FAILED,
        )
        store.save(failed_response)
        raise exc


def enqueue_test_job(message: str = "ping", connection: Redis | None = None) -> Job:
    """Enqueues a test job on the default queue."""
    q = get_queue(connection=connection)
    return q.enqueue(run_test_job, message)


def enqueue(analysis_id: str, page: PageData, connection: Redis | None = None) -> Job:
    """Enqueues a page analysis job on the default queue."""
    q = get_queue(connection=connection)
    return q.enqueue(run_analysis_job, analysis_id, page.model_dump(), job_id=analysis_id)
