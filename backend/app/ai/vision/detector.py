"""Estimates how likely an image is to be AI-generated (owner: Rareș).

TODO(Rareș):
- download the image with a timeout and a size limit
- cheap metadata checks first: C2PA content credentials, an EXIF "Software" field
  naming an AI tool, missing camera EXIF data
- run a pretrained detector from Hugging Face (try 2-3, keep the one that is most
  accurate on qa/images)
- put what you found in `signals`, so the user sees why an image was flagged
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings
from app.schemas import ImageResult

if TYPE_CHECKING:
    import torch
    from PIL import Image
    from transformers import ImageProcessingMixin, PreTrainedModel

MODEL_ID = "haywoodsloan/ai-image-detector-deploy"
DOWNLOAD_TIMEOUT_SECONDS = 10.0
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 64 * 1024
USER_AGENT = "OrderGuard/1.0"
AI_LABELS = {"ai", "artificial", "fake", "generated", "ai-generated", "ai_generated", "sd"}


class DownloadError(Exception):
    """Raised when an image cannot be downloaded within the timeout or size limit."""


def detect(image_url: str) -> ImageResult:
    if get_settings().ai_mode == "mock":
        return _mock_detect(image_url)
    return _real_detect(image_url)


def _mock_detect(image_url: str) -> ImageResult:
    # A stable fake score per URL, so the UI shows a mix of high and low values.
    probability = round(hashlib.sha256(image_url.encode()).digest()[0] / 255, 2)
    return ImageResult(url=image_url, ai_probability=probability, signals=["[MOCK] fake score"])


def _download_image(
    url: str,
    timeout: float | None = None,
    max_bytes: int | None = None,
) -> bytes:
    if timeout is None:
        timeout = DOWNLOAD_TIMEOUT_SECONDS
    if max_bytes is None:
        max_bytes = MAX_IMAGE_BYTES
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise DownloadError(f"Unsupported URL scheme: {parsed.scheme or 'none'}")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                raise DownloadError(
                    f"Image exceeds size limit ({int(content_length)} > {max_bytes} bytes)"
                )

            buffer = io.BytesIO()
            total = 0
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise DownloadError(f"Image exceeds size limit ({max_bytes} bytes)")
                buffer.write(chunk)
    except DownloadError:
        raise
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise DownloadError(str(reason)) from exc

    data = buffer.getvalue()
    if not data:
        raise DownloadError("Empty response body")
    return data


@lru_cache(maxsize=1)
def _load_detector(
    model_id: str = MODEL_ID,
) -> tuple[ImageProcessingMixin, PreTrainedModel, list[int], torch.device]:
    import torch
    from transformers import AutoImageProcessor, AutoModelForImageClassification

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForImageClassification.from_pretrained(model_id).to(device).eval()

    ai_indices = [
        int(idx)
        for idx, label in model.config.id2label.items()
        if label.strip().lower() in AI_LABELS
    ]
    if not ai_indices:
        raise RuntimeError(f"{model_id}: cannot map labels {model.config.id2label} to AI class")
    return processor, model, ai_indices, device


def _score_image(image: Image.Image) -> float:
    import torch

    processor, model, ai_indices, device = _load_detector()
    with torch.inference_mode():
        inputs = processor(images=image, return_tensors="pt").to(device)
        logits = model(**inputs).logits[0]
        probability = float(logits.softmax(-1)[ai_indices].sum())
    return max(0.0, min(1.0, probability))


def _real_detect(image_url: str) -> ImageResult:
    from PIL import Image, UnidentifiedImageError

    try:
        raw_bytes = _download_image(image_url)
    except DownloadError as exc:
        return ImageResult(
            url=image_url,
            ai_probability=0.0,
            signals=[f"Image download failed: {exc}"],
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb_image = img.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        return ImageResult(
            url=image_url,
            ai_probability=0.0,
            signals=[f"Invalid image data: {exc}"],
        )

    raw_score = _score_image(rgb_image)
    probability = round(raw_score, 2)
    return ImageResult(
        url=image_url,
        ai_probability=probability,
        signals=[f"Model score {probability:.2f} ({MODEL_ID})"],
    )
