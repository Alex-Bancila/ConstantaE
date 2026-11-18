"""An analysis keeps going when one of its parts fails (issue #15)."""

import logging
import threading

import pytest
from rq.worker import SimpleWorker

from app.ai.vision.detector import DOWNLOAD_FAILED_SIGNAL, INVALID_IMAGE_SIGNAL
from app.config import get_settings
from app.schemas import ImageResult, LegalReport, PageData
from app.services import analysis


def _raise(*args, **kwargs):
    raise RuntimeError("boom")


def _detector_failing_on(bad_url: str):
    def detect(url: str) -> ImageResult:
        if url == bad_url:
            raise RuntimeError("model crashed")
        return ImageResult(url=url, ai_probability=0.42, signals=["ok"])

    return detect


def test_one_failing_image_does_not_break_the_others(client, monkeypatch, example_page):
    monkeypatch.setattr("app.ai.vision.detect", _detector_failing_on(example_page["images"][0]))

    response = client.post("/analyze", json=example_page)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert [image["url"] for image in body["images"]] == example_page["images"]
    broken, healthy = body["images"]
    assert broken["aiProbability"] == 0.0
    assert broken["signals"] == ["Image analysis failed: RuntimeError"]
    assert healthy["aiProbability"] == 0.42
    assert body["trust"] is not None
    assert body["legal"] is not None


def test_failing_legal_report_still_returns_images_and_trust(client, monkeypatch, example_page):
    monkeypatch.setattr(analysis, "generate_report", _raise)

    response = client.post("/analyze", json=example_page)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["legal"] is None
    assert len(body["images"]) == len(example_page["images"])
    assert body["trust"] is not None


def test_failing_trust_checks_still_produce_the_legal_report(client, monkeypatch, example_page):
    received = []

    def report(page, failed_checks):
        received.append(failed_checks)
        return LegalReport(summary="Ai 14 zile.", citations=[])

    monkeypatch.setattr(analysis, "run_trust_checks", _raise)
    monkeypatch.setattr(analysis, "generate_report", report)

    body = client.post("/analyze", json=example_page).json()

    assert body["trust"] is None
    assert body["legal"]["summary"] == "Ai 14 zile."
    assert received == [[]]


def test_everything_failing_is_still_a_done_response(client, monkeypatch, example_page):
    monkeypatch.setattr("app.ai.vision.detect", _raise)
    monkeypatch.setattr(analysis, "run_trust_checks", _raise)
    monkeypatch.setattr(analysis, "generate_report", _raise)

    response = client.post("/analyze", json=example_page)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["trust"] is None
    assert body["legal"] is None
    assert all(image["signals"][0].startswith("Image analysis failed") for image in body["images"])


def test_failed_download_is_retried_on_the_next_analysis(client, monkeypatch, example_page):
    calls = []

    def detect(url: str) -> ImageResult:
        calls.append(url)
        return ImageResult(url=url, ai_probability=0.0, signals=[f"{DOWNLOAD_FAILED_SIGNAL}: 503"])

    monkeypatch.setattr("app.ai.vision.detect", detect)

    client.post("/analyze", json=example_page)
    client.post("/analyze", json=example_page)

    assert len(calls) == 2 * len(example_page["images"])


def test_crashed_image_is_retried_on_the_next_analysis(client, monkeypatch, example_page):
    monkeypatch.setattr("app.ai.vision.detect", _raise)
    client.post("/analyze", json=example_page)

    monkeypatch.setattr("app.ai.vision.detect", _detector_failing_on("none"))
    body = client.post("/analyze", json=example_page).json()

    assert [image["aiProbability"] for image in body["images"]] == [0.42, 0.42]


@pytest.mark.parametrize(
    ("signals", "failed"),
    [
        ([f"{DOWNLOAD_FAILED_SIGNAL}: HTTP 404"], True),
        ([f"{INVALID_IMAGE_SIGNAL}: cannot identify image file"], True),
        ([f"{analysis.IMAGE_FAILED_SIGNAL}: RuntimeError"], True),
        (["No camera EXIF data", "Model score 0.03 (model)"], False),
        ([], False),
    ],
)
def test_is_failed_image(signals, failed):
    result = ImageResult(url="https://example.com/a.jpg", ai_probability=0.0, signals=signals)
    assert analysis.is_failed_image(result) is failed


def test_images_and_legal_report_run_at_the_same_time(monkeypatch, example_page):
    image_started, legal_started = threading.Event(), threading.Event()

    def detect(url: str) -> ImageResult:
        image_started.set()
        if not legal_started.wait(timeout=5):
            raise TimeoutError("the legal report did not start while the images ran")
        return ImageResult(url=url, ai_probability=0.1, signals=[])

    def report(page, failed_checks):
        legal_started.set()
        if not image_started.wait(timeout=5):
            raise TimeoutError("the images did not start while the legal report ran")
        return LegalReport(summary="ok", citations=[])

    monkeypatch.setattr("app.ai.vision.detect", detect)
    monkeypatch.setattr(analysis, "generate_report", report)

    result = analysis.run("parallel-1", PageData.model_validate(example_page))

    assert [image.signals for image in result.images] == [[], []]
    assert result.legal is not None and result.legal.summary == "ok"


def test_each_analysis_logs_how_long_each_part_took(example_page, caplog):
    caplog.set_level(logging.INFO, logger="app.services.analysis")

    result, timings = analysis.run_timed("timed-1", PageData.model_validate(example_page))

    assert result.status == "done"
    assert timings.total_ms >= timings.trust_ms >= 0
    assert timings.total_ms >= max(timings.images_ms, timings.legal_ms)
    assert "analysis timed-1 (mock, 2 images)" in caplog.text
    assert "total=" in caplog.text


def test_partial_failure_in_the_worker_ends_done_not_failed(
    client, fake_redis, monkeypatch, example_page
):
    monkeypatch.setenv("ASYNC", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.ai.vision.detect", _detector_failing_on(example_page["images"][1]))
    monkeypatch.setattr(analysis, "generate_report", _raise)

    analysis_id = client.post("/analyze", json=example_page).json()["analysisId"]
    SimpleWorker(["default"], connection=fake_redis).work(burst=True)

    body = client.get(f"/analyze/{analysis_id}").json()
    assert body["status"] == "done"
    assert len(body["images"]) == len(example_page["images"])
    assert body["trust"] is not None
    assert body["legal"] is None
