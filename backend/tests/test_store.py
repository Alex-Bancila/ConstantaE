import time

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import AnalysisResponse, AnalysisStatus, PageData
from app.services import analysis
from app.workers import queue, store


def test_save_and_load(fake_redis, example_page):
    page = PageData.model_validate(example_page)
    result = analysis.run("test-save-id", page)

    store.save(result, connection=fake_redis)
    loaded = store.load("test-save-id", connection=fake_redis)

    assert loaded is not None
    assert loaded.analysis_id == "test-save-id"
    assert loaded.status == AnalysisStatus.DONE
    assert len(loaded.images) == len(page.images)
    assert loaded.trust == result.trust


def test_results_survive_api_restart(client, fake_redis, example_page):
    # Step 1: Initial API process handles POST /analyze and writes to Redis
    post_res = client.post("/analyze", json=example_page)
    assert post_res.status_code == 200
    analysis_id = post_res.json()["analysisId"]

    # Step 2: Simulate API server restart by instantiating a brand new TestClient
    restarted_client = TestClient(app)

    # Step 3: Restarted API fetches the analysis from Redis
    get_res = restarted_client.get(f"/analyze/{analysis_id}")
    assert get_res.status_code == 200
    assert get_res.json()["analysisId"] == analysis_id
    assert get_res.json()["status"] == "done"


def test_default_ttl_is_24_hours(fake_redis, example_page):
    page = PageData.model_validate(example_page)
    result = analysis.run("ttl-default-id", page)

    store.save(result, connection=fake_redis)
    ttl = store.get_ttl("ttl-default-id", connection=fake_redis)

    # 24 hours = 86400 seconds
    assert 86390 <= ttl <= 86400


def test_results_expire_after_set_ttl(fake_redis, example_page):
    page = PageData.model_validate(example_page)
    result = analysis.run("ttl-expire-id", page)

    # Save with 1 second TTL
    store.save(result, ttl=1, connection=fake_redis)
    assert store.load("ttl-expire-id", connection=fake_redis) is not None

    # Wait for expiration
    time.sleep(1.1)
    assert store.load("ttl-expire-id", connection=fake_redis) is None


def test_expired_analysis_returns_404_in_api(client, fake_redis, example_page):
    post_res = client.post("/analyze", json=example_page)
    analysis_id = post_res.json()["analysisId"]

    # Force expiration in Redis
    fake_redis.expire(f"analysis:{analysis_id}", 0)

    # API now returns 404 because the result has expired
    get_res = client.get(f"/analyze/{analysis_id}")
    assert get_res.status_code == 404
    assert get_res.json()["detail"] == "Analysis not found"


def test_worker_and_api_share_results(client, fake_redis, example_page):
    analysis_id = "shared-worker-analysis-id"
    page = PageData.model_validate(example_page)

    # Worker process executes the analysis job and writes to Redis store
    queue.run_analysis_job(analysis_id, page)

    # API process reads the result saved by the worker
    get_res = client.get(f"/analyze/{analysis_id}")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["analysisId"] == analysis_id
    assert body["status"] == "done"


def test_load_missing_and_delete(fake_redis):
    assert store.load("does-not-exist", connection=fake_redis) is None
    assert store.delete("does-not-exist", connection=fake_redis) is False

    # Save and then delete
    dummy = AnalysisResponse(analysis_id="to-delete", status=AnalysisStatus.PENDING)
    store.save(dummy, connection=fake_redis)
    assert store.load("to-delete", connection=fake_redis) is not None

    assert store.delete("to-delete", connection=fake_redis) is True
    assert store.load("to-delete", connection=fake_redis) is None
