"""Estimates how likely an image is to be AI-generated (owner: Rareș).

Runs cheap metadata checks first (C2PA content credentials, an EXIF "Software" field
naming an AI tool, and camera EXIF data), then scores the image with the pretrained
Hugging Face detector (`haywoodsloan/ai-image-detector-deploy`) and combines the
findings into `signals` and `ai_probability`.
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
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

# Minimum AI probability when metadata proves AI generation (C2PA AI marker or AI EXIF Software).
METADATA_AI_PROOF_MIN_PROBABILITY = 0.95

# EXIF tag IDs (TIFF / EXIF specification).
EXIF_MAKE = 0x010F
EXIF_MODEL = 0x0110
EXIF_SOFTWARE = 0x0131

# C2PA JUMBF box / XMP markers inside raw image bytes.
C2PA_MARKERS: tuple[bytes, ...] = (
    b"urn:c2pa:",
    b"c2pa.claim",
    b"c2pa.assertions",
    b"c2pa.signature",
    b"dcterms:provenance",
    b"jumb",
)

# C2PA digitalSourceType URIs and action strings that specifically indicate AI generation.
C2PA_AI_MARKERS: tuple[bytes, ...] = (
    b"trainedAlgorithmicMedia",
    b"compositeWithTrainedAlgorithmicMedia",
    b"algorithmicMedia",
    b"c2pa.ai_",
)

# Known AI image generators / tools that may appear in EXIF Software or XMP/PNG text chunks.
AI_SOFTWARE_KEYWORDS: tuple[str, ...] = (
    "midjourney",
    "dall-e",
    "dalle",
    "stable diffusion",
    "stablediffusion",
    "automatic1111",
    "comfyui",
    "invokeai",
    "firefly",
    "adobe firefly",
    "imagen",
    "flux",
    "leonardo",
    "ideogram",
    "recraft",
    "playground ai",
    "bing image creator",
    "novelai",
    "krea",
    "runway",
    "sora",
    "chatgpt",
    "openai",
    "gemini",
)


class DownloadError(Exception):
    """Raised when an image cannot be downloaded within the timeout or size limit."""


@dataclass
class MetadataFindings:
    signals: list[str] = field(default_factory=list)
    ai_proof: bool = False


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


def _clean_exif_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    return str(value).replace("\x00", "").strip()


def _has_c2pa_credentials(raw_bytes: bytes) -> tuple[bool, bool]:
    """Return (has_c2pa_manifest, c2pa_indicates_ai)."""
    lower_bytes = raw_bytes.lower()
    has_c2pa = any(marker.lower() in lower_bytes for marker in C2PA_MARKERS)
    if not has_c2pa:
        return False, False
    indicates_ai = any(marker.lower() in lower_bytes for marker in C2PA_AI_MARKERS) or any(
        kw.encode("utf-8") in lower_bytes for kw in AI_SOFTWARE_KEYWORDS
    )
    return True, indicates_ai


def _match_ai_software(software: str) -> str | None:
    lowered = software.lower()
    for keyword in AI_SOFTWARE_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def _inspect_metadata(raw_bytes: bytes, image: Image.Image) -> MetadataFindings:
    """Run cheap metadata checks: C2PA credentials, EXIF Software, and camera EXIF."""
    findings = MetadataFindings()

    # 1. C2PA Content Credentials check
    has_c2pa, c2pa_ai = _has_c2pa_credentials(raw_bytes)
    if has_c2pa:
        if c2pa_ai:
            findings.signals.append("C2PA content credentials indicate AI generation")
        else:
            findings.signals.append("C2PA content credentials present")
        findings.ai_proof = True

    # 2. EXIF Software & Camera Make/Model check
    exif = image.getexif()
    software = _clean_exif_text(exif.get(EXIF_SOFTWARE))
    if not software:
        # Also check PNG/WebP info dictionary if EXIF Software tag wasn't populated
        software = _clean_exif_text(image.info.get("Software") or image.info.get("software"))

    if software and _match_ai_software(software):
        findings.signals.append(f"EXIF Software names AI tool ({software})")
        findings.ai_proof = True

    make = _clean_exif_text(exif.get(EXIF_MAKE))
    model = _clean_exif_text(exif.get(EXIF_MODEL))
    if make or model:
        camera = (
            model
            if (make and model.lower().startswith(make.lower()))
            else f"{make} {model}".strip()
        )
        findings.signals.append(f"Camera EXIF data present ({camera})")
    else:
        findings.signals.append("No camera EXIF data")

    return findings


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
            metadata = _inspect_metadata(raw_bytes, img)
            rgb_image = img.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        return ImageResult(
            url=image_url,
            ai_probability=0.0,
            signals=[f"Invalid image data: {exc}"],
        )

    model_score = round(_score_image(rgb_image), 2)
    final_probability = (
        max(model_score, METADATA_AI_PROOF_MIN_PROBABILITY) if metadata.ai_proof else model_score
    )
    signals = [*metadata.signals, f"Model score {model_score:.2f} ({MODEL_ID})"]
    return ImageResult(
        url=image_url,
        ai_probability=final_probability,
        signals=signals,
    )
