"""Evaluate the final detector (metadata checks + haywoodsloan SwinV2 model) on labeled images.

Prints a Markdown summary (accuracy, precision, recall, ms/image, confusion matrix, and
per-image signals) both as saved on disk (with original metadata / C2PA / EXIF intact)
and when metadata is stripped (simulating websites that strip C2PA/EXIF on upload).

Usage (from backend/):

    python scripts/evaluate_detector.py
    python scripts/evaluate_detector.py --images ../qa/images_extra
"""

from __future__ import annotations

import argparse
import io
import os
import statistics
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai.vision import detector  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.schemas import ImageResult  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGES = REPO_ROOT / "qa" / "images"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


@dataclass
class EvalRow:
    rel_path: str
    is_ai: bool
    result: ImageResult
    ms: float


class _BytesResponse:
    def __init__(self, body: bytes) -> None:
        self._stream = io.BytesIO(body)
        self.headers = {"Content-Length": str(len(body))}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> _BytesResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self._stream.close()


def strip_to_jpeg(raw_bytes: bytes, quality: int = 90) -> bytes:
    with Image.open(io.BytesIO(raw_bytes)) as img:
        rgb = img.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def collect_files(root: Path) -> list[tuple[Path, bool]]:
    items: list[tuple[Path, bool]] = []
    for folder, is_ai in (("ai", True), ("real", False)):
        directory = root / folder
        if not directory.is_dir():
            raise SystemExit(f"Missing folder: {directory}")
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() in IMAGE_SUFFIXES:
                items.append((path, is_ai))
    if not any(is_ai for _, is_ai in items) or all(is_ai for _, is_ai in items):
        raise SystemExit(f"Need images in both {root / 'ai'} and {root / 'real'}")
    return items


def run_suite(
    files: list[tuple[Path, bool]],
    *,
    strip_metadata: bool = False,
) -> list[EvalRow]:
    payload_by_url: dict[str, bytes] = {}
    for path, _ in files:
        url = f"https://eval.local/{path.parent.name}/{path.name}"
        raw = path.read_bytes()
        payload_by_url[url] = strip_to_jpeg(raw) if strip_metadata else raw

    orig_urlopen = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=10: _BytesResponse(payload_by_url[req.full_url])  # type: ignore[assignment]
    try:
        # Warm up model once before timing
        first_url = next(iter(payload_by_url))
        detector.detect(first_url)

        rows: list[EvalRow] = []
        for path, is_ai in files:
            url = f"https://eval.local/{path.parent.name}/{path.name}"
            start = time.perf_counter()
            res = detector.detect(url)
            elapsed_ms = (time.perf_counter() - start) * 1000
            rows.append(
                EvalRow(
                    rel_path=f"{path.parent.name}/{path.name}",
                    is_ai=is_ai,
                    result=res,
                    ms=elapsed_ms,
                )
            )
        return rows
    finally:
        urllib.request.urlopen = orig_urlopen  # type: ignore[assignment]


def summarize(rows: list[EvalRow], threshold: float = 0.5) -> dict[str, float | int]:
    tp = sum(r.is_ai and r.result.ai_probability >= threshold for r in rows)
    fp = sum((not r.is_ai) and r.result.ai_probability >= threshold for r in rows)
    fn = sum(r.is_ai and r.result.ai_probability < threshold for r in rows)
    tn = len(rows) - tp - fp - fn
    return {
        "accuracy": (tp + tn) / len(rows),
        "precision": tp / (tp + fp) if (tp + fp) else 0.0,
        "recall": tp / (tp + fn) if (tp + fn) else 0.0,
        "ms": statistics.median(r.ms for r in rows),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--per-image", action="store_true")
    args = parser.parse_args()

    os.environ["AI_MODE"] = "real"
    get_settings.cache_clear()

    files = collect_files(args.images)
    n_ai = sum(is_ai for _, is_ai in files)
    n_real = len(files) - n_ai

    full_rows = run_suite(files, strip_metadata=False)
    stripped_rows = run_suite(files, strip_metadata=True)

    m_full = summarize(full_rows, args.threshold)
    m_strip = summarize(stripped_rows, args.threshold)

    print(
        f"Dataset: `{args.images.name}` — {len(files)} images ({n_ai} AI, {n_real} real), "
        f"threshold {args.threshold}, model `{detector.MODEL_ID}`.\n"
    )
    print("| Pipeline Mode | Accuracy | Precision | Recall | ms/image | TP / FP / TN / FN |")
    print("|---|---:|---:|---:|---:|---|")
    print(
        f"| **Full detector (metadata + model)** | **{m_full['accuracy']:.0%}** | "
        f"**{m_full['precision']:.0%}** | **{m_full['recall']:.0%}** | {m_full['ms']:.0f} | "
        f"{m_full['tp']} / {m_full['fp']} / {m_full['tn']} / {m_full['fn']} |"
    )
    print(
        f"| Model only (metadata stripped to JPEG q90) | {m_strip['accuracy']:.0%} | "
        f"{m_strip['precision']:.0%} | {m_strip['recall']:.0%} | {m_strip['ms']:.0f} | "
        f"{m_strip['tp']} / {m_strip['fp']} / {m_strip['tn']} / {m_strip['fn']} |"
    )

    if args.per_image:
        print("\nPer-image results (full detector):\n")
        print("| Image | Label | aiProbability | Signals |")
        print("|---|---|---:|---|")
        for r in full_rows:
            label = "ai" if r.is_ai else "real"
            sigs = "; ".join(r.result.signals)
            print(f"| `{r.rel_path}` | {label} | {r.result.ai_probability:.2f} | {sigs} |")


if __name__ == "__main__":
    main()
