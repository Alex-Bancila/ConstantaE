"""Compare pretrained AI-image detectors on the labeled images in qa/images.

Every image is first re-encoded to JPEG (quality 90 by default), so a detector cannot
tell the classes apart by file format (our AI images are PNG, most real ones are WebP
or JPEG). The result is a Markdown table for the PR description on stdout; progress
goes to stderr.

Usage (from backend/, after `pip install -r requirements-vision.txt`):

    python scripts/compare_detectors.py
    python scripts/compare_detectors.py --max-side 512 --per-image

"AI" is the positive class: precision = how many images flagged as AI really are AI,
recall = how many AI images were caught.
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGES = REPO_ROOT / "qa" / "images"
DEFAULT_MODELS = [
    "Ateeqq/ai-vs-human-image-detector",  # SigLIP, Apache-2.0 (main candidate)
    "haywoodsloan/ai-image-detector-deploy",  # SwinV2, Apache-2.0
    "Organika/sdxl-detector",  # Swin
]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

# Each model names its classes differently; map them to "ai" / "real".
AI_LABELS = {"ai", "artificial", "fake", "generated", "ai-generated", "ai_generated", "sd"}
REAL_LABELS = {"hum", "human", "real", "natural", "nature", "authentic"}


@dataclass
class Sample:
    path: Path
    is_ai: bool
    image: Image.Image


@dataclass
class Prediction:
    sample: Sample
    ai_probability: float
    ms: float


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def reencode(path: Path, quality: int, max_side: int | None) -> Image.Image:
    """Decode any format, optionally downscale, and round-trip through JPEG."""
    with Image.open(path) as img:
        img = img.convert("RGB")
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    jpeg = Image.open(buffer)
    jpeg.load()
    return jpeg


def load_samples(root: Path, quality: int, max_side: int | None) -> list[Sample]:
    samples = []
    for folder, is_ai in (("ai", True), ("real", False)):
        directory = root / folder
        if not directory.is_dir():
            raise SystemExit(f"Missing folder: {directory}")
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() in IMAGE_SUFFIXES:
                samples.append(Sample(path, is_ai, reencode(path, quality, max_side)))
    if not any(s.is_ai for s in samples) or all(s.is_ai for s in samples):
        raise SystemExit(f"Need images in both {root / 'ai'} and {root / 'real'}")
    return samples


def ai_label_indices(model_id: str, id2label: dict[int, str]) -> list[int]:
    ai, unknown = [], []
    for index, label in id2label.items():
        name = label.strip().lower()
        if name in AI_LABELS:
            ai.append(int(index))
        elif name not in REAL_LABELS:
            unknown.append(label)
    if unknown or not ai:
        raise SystemExit(f"{model_id}: cannot map labels {id2label} to ai/real")
    return ai


def pick_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def run_model(
    model_id: str, samples: list[Sample], device: torch.device, warmup: int
) -> list[Prediction]:
    log(f"Loading {model_id} ...")
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForImageClassification.from_pretrained(model_id).to(device).eval()
    ai_indices = ai_label_indices(model_id, model.config.id2label)
    log(f"  labels: {model.config.id2label} -> AI = {ai_indices}")

    def ai_probability(image: Image.Image) -> float:
        inputs = processor(images=image, return_tensors="pt").to(device)
        logits = model(**inputs).logits[0]
        return float(logits.softmax(-1)[ai_indices].sum())

    predictions = []
    with torch.inference_mode():
        for _ in range(warmup):  # first calls are slow (lazy init, kernel selection)
            ai_probability(samples[0].image)
        sync(device)
        for sample in samples:
            start = time.perf_counter()
            probability = ai_probability(sample.image)
            sync(device)
            predictions.append(
                Prediction(sample, probability, (time.perf_counter() - start) * 1000)
            )
    return predictions


def metrics(predictions: list[Prediction], threshold: float) -> dict[str, float]:
    tp = sum(p.sample.is_ai and p.ai_probability >= threshold for p in predictions)
    fp = sum(not p.sample.is_ai and p.ai_probability >= threshold for p in predictions)
    fn = sum(p.sample.is_ai and p.ai_probability < threshold for p in predictions)
    tn = len(predictions) - tp - fp - fn
    return {
        "accuracy": (tp + tn) / len(predictions),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "ms": statistics.median(p.ms for p in predictions),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--images",
        type=Path,
        default=DEFAULT_IMAGES,
        help="folder with ai/ and real/ subfolders (default: qa/images)",
    )
    parser.add_argument(
        "--models", nargs="+", default=DEFAULT_MODELS, help="Hugging Face model ids to compare"
    )
    parser.add_argument("--quality", type=int, default=90, help="JPEG quality (default: 90)")
    parser.add_argument(
        "--max-side",
        type=int,
        default=None,
        help="also downscale so the longest side is at most this many pixels",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="AI probability at or above which an image counts as AI",
    )
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, cuda:0, ...")
    parser.add_argument("--warmup", type=int, default=2, help="untimed runs per model")
    parser.add_argument("--threads", type=int, default=None, help="torch CPU threads")
    parser.add_argument(
        "--per-image", action="store_true", help="also print each image's AI probability per model"
    )
    args = parser.parse_args()

    if args.threads:
        torch.set_num_threads(args.threads)
    device = pick_device(args.device)
    samples = load_samples(args.images, args.quality, args.max_side)
    n_ai = sum(s.is_ai for s in samples)
    log(f"{len(samples)} images ({n_ai} ai, {len(samples) - n_ai} real), device {device}")

    results = {
        model_id: run_model(model_id, samples, device, args.warmup) for model_id in args.models
    }

    resize = f", longest side <= {args.max_side}px" if args.max_side else ""
    print(
        f"Images: {len(samples)} ({n_ai} AI, {len(samples) - n_ai} real), re-encoded to "
        f"JPEG q{args.quality}{resize}. Threshold {args.threshold}. Device: {device} "
        f"(torch {torch.__version__}, {torch.get_num_threads()} threads).\n"
    )
    print("| Model | Accuracy | Precision | Recall | ms/image | TP / FP / TN / FN |")
    print("|---|---:|---:|---:|---:|---|")
    for model_id, predictions in results.items():
        m = metrics(predictions, args.threshold)
        print(
            f"| `{model_id}` | {m['accuracy']:.0%} | {m['precision']:.0%} | "
            f"{m['recall']:.0%} | {m['ms']:.0f} | "
            f"{m['tp']} / {m['fp']} / {m['tn']} / {m['fn']} |"
        )
    print(
        "\nms/image = median of preprocessing + forward pass, one image at a time, "
        "after warm-up; excludes model loading."
    )

    if args.per_image:
        short = [model_id.split("/")[-1] for model_id in results]
        print("\nAI probability per image:\n")
        print("| Image | Label | " + " | ".join(short) + " |")
        print("|---|---|" + "---:|" * len(short))
        for i, sample in enumerate(samples):
            cells = " | ".join(f"{preds[i].ai_probability:.2f}" for preds in results.values())
            label = "ai" if sample.is_ai else "real"
            print(f"| {sample.path.parent.name}/{sample.path.name} | {label} | {cells} |")


if __name__ == "__main__":
    main()
