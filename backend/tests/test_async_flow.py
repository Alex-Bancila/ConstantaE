from rq.job import JobStatus
from rq.worker import SimpleWorker

from app.config import get_settings
from app.workers import queue


def test_async_true_returns_pending_immediately(client, monkeypatch, example_page):
    monkeypatch.setenv("ASYNC", "true")
    get_settings.cache_clear()

    res = client.post("/analyze", json=example_page)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "pending"
    assert "analysisId" in data
    assert data["images"] == []
    assert data.get("trust") is None
    assert data.get("legal") is None


def test_worker_finishes_analysis_and_get_returns_done(
    client, fake_redis, monkeypatch, example_page
):
    monkeypatch.setenv("ASYNC", "true")
    get_settings.cache_clear()

    # Step 1: POST /analyze returns pending immediately
    post_res = client.post("/analyze", json=example_page)
    assert post_res.status_code == 200
    analysis_id = post_res.json()["analysisId"]
    assert post_res.json()["status"] == "pending"

    # Pending in store initially
    initial_get = client.get(f"/analyze/{analysis_id}")
    assert initial_get.status_code == 200
    assert initial_get.json()["status"] == "pending"

    # Step 2: Worker processes the job
    worker = SimpleWorker(["default"], connection=fake_redis)
    worker.work(burst=True)

    # Step 3: GET /analyze/{id} now returns done with full analysis
    final_get = client.get(f"/analyze/{analysis_id}")
    assert final_get.status_code == 200
    final_data = final_get.json()
    assert final_data["status"] == "done"
    assert len(final_data["images"]) == len(example_page["images"])
    assert final_data["trust"] is not None
    assert final_data["legal"] is not None


def test_failure_ends_in_failed_never_stuck_pending(client, fake_redis, monkeypatch, example_page):
    monkeypatch.setenv("ASYNC", "true")
    get_settings.cache_clear()

    # Simulate an unexpected failure in the analysis pipeline
    def mock_run_failure(analysis_id, page):
        raise RuntimeError("Vision model GPU out of memory")

    monkeypatch.setattr("app.services.analysis.run", mock_run_failure)

    post_res = client.post("/analyze", json=example_page)
    analysis_id = post_res.json()["analysisId"]

    # Worker executes and handles failure
    worker = SimpleWorker(["default"], connection=fake_redis)
    worker.work(burst=True)

    # Result in store must now be failed, never stuck in pending
    get_res = client.get(f"/analyze/{analysis_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "failed"


def test_rq_job_failure_detected_by_get(client, fake_redis, monkeypatch, example_page):
    monkeypatch.setenv("ASYNC", "true")
    get_settings.cache_clear()

    post_res = client.post("/analyze", json=example_page)
    analysis_id = post_res.json()["analysisId"]

    # Emulate an external/unhandled RQ job failure
    job = queue.get_job(analysis_id, connection=fake_redis)
    assert job is not None
    job.set_status(JobStatus.FAILED)

    # GET /analyze/{id} inspects the failed job and updates store to failed
    get_res = client.get(f"/analyze/{analysis_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "failed"


def test_async_false_still_works_as_demo_fallback(client, monkeypatch, example_page):
    monkeypatch.setenv("ASYNC", "false")
    get_settings.cache_clear()

    post_res = client.post("/analyze", json=example_page)
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "done"
    assert len(post_data["images"]) == len(example_page["images"])
    assert post_data["trust"] is not None
    assert post_data["legal"] is not None

    get_res = client.get(f"/analyze/{post_data['analysisId']}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "done"
