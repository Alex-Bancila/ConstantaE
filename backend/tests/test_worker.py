import sys

import fakeredis
import pytest
from rq.worker import SimpleWorker, Worker

from app.config import get_settings
from app.schemas import PageData
from app.workers import store
from app.workers.queue import (
    enqueue,
    enqueue_test_job,
    get_queue,
    get_redis_connection,
    run_test_job,
)
from app.workers.worker import (
    create_worker,
    get_worker_class,
    run_test_end_to_end,
)


@pytest.fixture
def fake_redis():
    server = fakeredis.FakeServer()
    return fakeredis.FakeRedis(server=server)


def test_redis_connection_from_settings(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/3")
    get_settings.cache_clear()
    conn = get_redis_connection()
    assert conn.connection_pool.connection_kwargs.get("db") == 3


def test_worker_class_by_platform():
    worker_cls = get_worker_class()
    if sys.platform == "win32":
        assert worker_cls is SimpleWorker
    else:
        assert worker_cls is Worker


def test_test_job_runs_end_to_end(fake_redis):
    job = enqueue_test_job("marius-check", connection=fake_redis)
    assert job.get_status() == "queued"

    worker = create_worker(["default"], connection=fake_redis)
    worker.work(burst=True)

    job.refresh()
    assert job.get_status() == "finished"
    assert job.return_value() == "pong: marius-check"


def test_analysis_job_runs_end_to_end(fake_redis, example_page):
    analysis_id = "test-analysis-456"
    page = PageData.model_validate(example_page)

    job = enqueue(analysis_id, page, connection=fake_redis)
    assert job.get_status() == "queued"

    worker = create_worker(["default"], connection=fake_redis)
    worker.work(burst=True)

    job.refresh()
    assert job.get_status() == "finished"

    loaded = store.load(analysis_id)
    assert loaded is not None
    assert loaded.status == "done"
    assert loaded.analysis_id == analysis_id
    assert len(loaded.images) == len(page.images)


def test_run_test_end_to_end_function(fake_redis):
    assert run_test_end_to_end(connection=fake_redis) is True


def test_get_queue_returns_rq_queue(fake_redis):
    q = get_queue("custom-queue", connection=fake_redis)
    assert q.name == "custom-queue"
    job = q.enqueue(run_test_job, "direct")
    assert job.get_status() == "queued"
