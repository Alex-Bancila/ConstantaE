"""Estimates how likely an image is to be AI-generated (owner: Rareș).

TODO(Rareș):
- download the image with a timeout and a size limit
- cheap metadata checks first: C2PA content credentials, an EXIF "Software" field
  naming an AI tool, missing camera EXIF data
- run a pretrained detector from Hugging Face (try 2-3, keep the one that is most
  accurate on qa/images)
- put what you found in `signals`, so the user sees why an image was flagged
"""

import hashlib

from app.config import get_settings
from app.schemas import ImageResult


def detect(image_url: str) -> ImageResult:
    if get_settings().ai_mode == "mock":
        return _mock_detect(image_url)
    raise NotImplementedError("TODO(Rareș): real image detection. Use AI_MODE=mock for now.")


def _mock_detect(image_url: str) -> ImageResult:
    # A stable fake score per URL, so the UI shows a mix of high and low values.
    probability = round(hashlib.sha256(image_url.encode()).digest()[0] / 255, 2)
    return ImageResult(url=image_url, ai_probability=probability, signals=["[MOCK] fake score"])
