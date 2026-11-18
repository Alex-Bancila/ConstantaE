"""Background job queue for the slow AI work (owner: Marius).

Redis-backed queue using RQ.
"""

from typing import Any

from redis import Redis
from rq import Queue
from rq.job import Job

from app.config import get_settings
from app.schemas import PageData


def get_redis_connection() -> Redis:
    """Creates a Redis client from the REDIS_URL setting."""
    settings = get_settings()
    url = settings.redis_url or "redis://localhost:6379"
    return Redis.from_url(url)


def get_queue(name: str = "default", connection: Redis | None = None) -> Queue:
    """Returns an RQ Queue connected to Redis."""
    conn = connection or get_redis_connection()
    return Queue(name, connection=conn)


def run_test_job(message: str = "ping") -> str:
    """A lightweight test job to verify worker execution end-to-end."""
    return f"pong: {message}"


def run_analysis_job(analysis_id: str, page_data: dict[str, Any] | PageData) -> dict[str, Any]:
    """Processes a page analysis job and stores the completed result."""
    from app.services.analysis import run
    from app.workers import store

    if isinstance(page_data, dict):
        page = PageData.model_validate(page_data)
    else:
        page = page_data

    result = run(analysis_id, page)
    store.save(result)
    return result.model_dump(mode="json", by_alias=True)


def enqueue_test_job(message: str = "ping", connection: Redis | None = None) -> Job:
    """Enqueues a test job on the default queue."""
    q = get_queue(connection=connection)
    return q.enqueue(run_test_job, message)


def enqueue(analysis_id: str, page: PageData, connection: Redis | None = None) -> Job:
    """Enqueues a page analysis job on the default queue."""
    q = get_queue(connection=connection)
    return q.enqueue(run_analysis_job, analysis_id, page.model_dump())
