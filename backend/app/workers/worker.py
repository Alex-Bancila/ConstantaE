"""Worker process for background jobs (owner: Marius).

Starts an RQ worker listening to Redis.
On Windows, SimpleWorker is used because os.fork is not available.
On Linux/macOS, standard Worker is used.
"""

import argparse
import logging
import sys

from redis import Redis
from rq import Queue, Worker
from rq.worker import SimpleWorker

from app.config import get_settings
from app.workers.queue import (
    enqueue_test_job,
    get_redis_connection,
)

logger = logging.getLogger("worker")


def get_worker_class() -> type[Worker]:
    """Returns SimpleWorker on Windows, standard Worker on POSIX platforms."""
    if sys.platform == "win32":
        return SimpleWorker
    return Worker


def create_worker(
    queues: list[str] | None = None,
    connection: Redis | None = None,
) -> Worker:
    """Instantiates the appropriate worker for the platform."""
    conn = connection or get_redis_connection()
    queue_names = queues or ["default"]
    q_instances = [Queue(name, connection=conn) for name in queue_names]
    worker_cls = get_worker_class()
    return worker_cls(q_instances, connection=conn)


def run_worker(
    queues: list[str] | None = None,
    burst: bool = False,
    connection: Redis | None = None,
) -> None:
    """Starts the worker process to process jobs."""
    conn = connection or get_redis_connection()
    settings = get_settings()
    url = settings.redis_url or "redis://localhost:6379"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Connecting to Redis at %s", url)

    try:
        conn.ping()
        logger.info("Connected to Redis successfully.")
    except Exception as exc:
        logger.error(
            "Could not connect to Redis at %s: %s\n"
            "Ensure Redis is running (e.g. docker run -d -p 6379:6379 redis:alpine).",
            url,
            exc,
        )
        sys.exit(1)

    worker = create_worker(queues=queues, connection=conn)
    logger.info(
        "Starting %s on queue(s): %s (burst=%s)",
        worker.__class__.__name__,
        queues or ["default"],
        burst,
    )
    worker.work(burst=burst)


def run_test_end_to_end(connection: Redis | None = None) -> bool:
    """Enqueues a test job and runs the worker in burst mode to verify end-to-end."""
    logging.basicConfig(level=logging.INFO)
    conn = connection or get_redis_connection()
    settings = get_settings()
    url = settings.redis_url or "redis://localhost:6379"

    try:
        conn.ping()
    except Exception as exc:
        print(f"Error connecting to Redis at {url}: {exc}")
        print("Ensure Redis is running (e.g. docker run -d -p 6379:6379 redis:alpine)")
        return False

    print("1. Enqueuing test job...")
    job = enqueue_test_job("ping-test", connection=conn)
    print(f"   Job enqueued with ID: {job.id}")

    print("2. Starting worker in burst mode to process job...")
    worker = create_worker(["default"], connection=conn)
    worker.work(burst=True)

    job.refresh()
    result = job.return_value() if callable(getattr(job, "return_value", None)) else job.result
    print(f"3. Job status: {job.get_status()}")
    print(f"   Job result: {result}")

    if job.get_status() == "finished" and result == "pong: ping-test":
        print("SUCCESS: Test job ran end to end successfully!")
        return True

    print("FAILED: Job did not finish as expected.")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="ConstantaE background worker")
    parser.add_argument(
        "queues",
        nargs="*",
        default=["default"],
        help="Queue names to listen on (default: 'default')",
    )
    parser.add_argument(
        "--burst",
        action="store_true",
        help="Run in burst mode (terminate once all jobs are processed)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run an end-to-end test job verification and exit",
    )
    args = parser.parse_args()

    if args.test:
        success = run_test_end_to_end()
        sys.exit(0 if success else 1)
    else:
        run_worker(queues=args.queues, burst=args.burst)


if __name__ == "__main__":
    main()
