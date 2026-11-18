"""Tests for AI-generated image detection (AI_MODE=real and AI_MODE=mock)."""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from app.ai.vision import detector
from app.config import REPO_ROOT, get_settings


class _FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self._stream = io.BytesIO(body)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self._stream.close()


def _make_jpeg_bytes(color: tuple[int, int, int] = (120, 180, 210)) -> bytes:
    img = Image.new("RGB", (32, 32), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture
def real_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_MODE", "real")
    get_settings.cache_clear()
    detector._load_detector.cache_clear()
    yield
    detector._load_detector.cache_clear()
    get_settings.cache_clear()


def test_mock_mode_returns_stable_score():
    result = detector.detect("https://example.com/photo.jpg")
    assert 0.0 <= result.ai_probability <= 1.0
    assert result.signals == ["[MOCK] fake score"]


def test_real_mode_scores_small_images_and_loads_model_once(
    real_mode: None, monkeypatch: pytest.MonkeyPatch
):
    load_calls = 0

    class DummyProcessor:
        def __call__(self, images, return_tensors: str = "pt"):
            return SimpleNamespace(to=lambda device: {"pixel_values": torch.zeros((1, 3, 8, 8))})

    class DummyModel:
        config = SimpleNamespace(id2label={0: "artificial", 1: "real"})

        def to(self, device):
            return self

        def eval(self):
            return self

        def __call__(self, **inputs):
            # Logits [2.0, 0.0] -> softmax[0] ~= 0.88
            return SimpleNamespace(logits=torch.tensor([[2.0, 0.0]]))

    def fake_from_pretrained_processor(model_id: str):
        nonlocal load_calls
        load_calls += 1
        return DummyProcessor()

    monkeypatch.setattr(
        "transformers.AutoImageProcessor.from_pretrained", fake_from_pretrained_processor
    )
    monkeypatch.setattr(
        "transformers.AutoModelForImageClassification.from_pretrained",
        lambda model_id: DummyModel(),
    )

    samples = [
        REPO_ROOT / "qa" / "images" / "real" / "shoe_2.jpg",
        REPO_ROOT / "qa" / "images" / "real" / "shoe_3.jpg",
    ]
    payloads = {
        f"https://example.com/{path.name}": path.read_bytes() for path in samples if path.exists()
    }
    if not payloads:
        payloads = {
            "https://example.com/a.jpg": _make_jpeg_bytes((200, 50, 50)),
            "https://example.com/b.jpg": _make_jpeg_bytes((50, 200, 50)),
        }

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=10: _FakeResponse(payloads[req.full_url]),
    )

    for url in payloads:
        result = detector.detect(url)
        assert result.url == url
        assert 0.0 <= result.ai_probability <= 1.0
        assert result.ai_probability == 0.88
        assert any("Model score 0.88" in s for s in result.signals)

    # Model is loaded once across multiple detect() calls.
    assert load_calls == 1


def test_download_timeout_returns_clear_signal(real_mode: None, monkeypatch: pytest.MonkeyPatch):
    def raise_timeout(req, timeout=10):
        raise TimeoutError("timed out after 10s")

    monkeypatch.setattr(urllib.request, "urlopen", raise_timeout)

    result = detector.detect("https://example.com/slow.jpg")
    assert result.ai_probability == 0.0
    assert len(result.signals) == 1
    assert "Image download failed" in result.signals[0]
    assert "timed out" in result.signals[0]


def test_download_http_error_returns_clear_signal(real_mode: None, monkeypatch: pytest.MonkeyPatch):
    def raise_404(req, timeout=10):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(urllib.request, "urlopen", raise_404)

    result = detector.detect("https://example.com/missing.jpg")
    assert result.ai_probability == 0.0
    assert result.signals == ["Image download failed: HTTP 404"]


def test_download_size_limit_exceeded_via_header_returns_clear_signal(
    real_mode: None, monkeypatch: pytest.MonkeyPatch
):
    too_big = str(detector.MAX_IMAGE_BYTES + 1)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=10: _FakeResponse(b"tiny", headers={"Content-Length": too_big}),
    )

    result = detector.detect("https://example.com/huge.jpg")
    assert result.ai_probability == 0.0
    assert any("exceeds size limit" in s for s in result.signals)


def test_download_size_limit_exceeded_via_stream_returns_clear_signal(
    real_mode: None, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(detector, "MAX_IMAGE_BYTES", 1024)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=10: _FakeResponse(b"x" * 2048),
    )

    result = detector.detect("https://example.com/stream-huge.jpg")
    assert result.ai_probability == 0.0
    assert any("exceeds size limit" in s for s in result.signals)


def test_invalid_image_bytes_returns_clear_signal(real_mode: None, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=10: _FakeResponse(b"not an image at all"),
    )

    result = detector.detect("https://example.com/corrupt.jpg")
    assert result.ai_probability == 0.0
    assert any("Invalid image data" in s for s in result.signals)


def test_real_haywoodsloan_model_on_small_images(real_mode: None, monkeypatch: pytest.MonkeyPatch):
    """End-to-end check with the actual haywoodsloan model on two small images."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    samples = {
        "https://example.com/real.jpg": _make_jpeg_bytes((40, 120, 200)),
        "https://example.com/shoe.jpg": (
            REPO_ROOT / "qa" / "images" / "real" / "shoe_3.jpg"
        ).read_bytes()
        if (REPO_ROOT / "qa" / "images" / "real" / "shoe_3.jpg").exists()
        else _make_jpeg_bytes((200, 100, 40)),
    }
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=10: _FakeResponse(samples[req.full_url]),
    )

    first = detector.detect("https://example.com/real.jpg")
    second = detector.detect("https://example.com/shoe.jpg")

    for res in (first, second):
        assert 0.0 <= res.ai_probability <= 1.0
        assert any(detector.MODEL_ID in s and "Model score" in s for s in res.signals)

    assert detector._load_detector.cache_info().hits == 1
    assert detector._load_detector.cache_info().misses == 1
