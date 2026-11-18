"""Download a balanced sample of real and AI images from Hugging Face for local testing.

Uses `tellif/ai_vs_real_image_semantically_similar`, which pairs real photographs with
AI images across 11 modern generators (Flux, Gemini, Imagen 4, SD 3.5, Recraft, Ideogram,
etc.). By default saves 50 AI + 50 real images into `qa/images_extra/` so you can run:

    python scripts/download_sample_images.py
    python scripts/compare_detectors.py --images ../qa/images_extra
"""

from __future__ import annotations

import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "qa" / "images_extra"
DATASET_ID = "tellif/ai_vs_real_image_semantically_similar"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def pick_balanced_ai(fake_files: list[str], count: int, rng: random.Random) -> list[str]:
    """Pick AI images evenly across all generator subfolders."""
    by_generator: dict[str, list[str]] = defaultdict(list)
    for path in sorted(fake_files):
        parts = path.split("/")
        generator = parts[2] if len(parts) > 2 else "ai"
        by_generator[generator].append(path)

    for files in by_generator.values():
        rng.shuffle(files)

    picked: list[str] = []
    generators = sorted(by_generator)
    while len(picked) < count and any(by_generator.values()):
        for gen in generators:
            if by_generator[gen] and len(picked) < count:
                picked.append(by_generator[gen].pop())
    return picked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="destination folder (creates ai/ and real/ inside; default: qa/images_extra)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="number of images per class to download (default: 50 -> 50 AI + 50 real)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="random seed for reproducible sampling"
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    api = HfApi()
    print(f"Listing files in {DATASET_ID} ...")
    all_files = [
        f
        for f in api.list_repo_files(DATASET_ID, repo_type="dataset")
        if Path(f).suffix.lower() in IMAGE_SUFFIXES
    ]

    real_files = sorted(f for f in all_files if f.startswith("eval/real/"))
    fake_files = sorted(f for f in all_files if f.startswith("eval/fake/"))
    rng.shuffle(real_files)

    selected_real = real_files[: args.count]
    selected_ai = pick_balanced_ai(fake_files, args.count, rng)

    for subfolder, selected in (("real", selected_real), ("ai", selected_ai)):
        target_dir = args.out / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {len(selected)} {subfolder} images to {target_dir} ...")
        for i, repo_path in enumerate(selected, 1):
            parts = repo_path.split("/")
            prefix = parts[2] if subfolder == "ai" and len(parts) > 2 else "real"
            ext = Path(repo_path).suffix.lower()
            dest = target_dir / f"{prefix}_{i:03d}{ext}"
            if dest.exists():
                continue
            cached = hf_hub_download(DATASET_ID, repo_path, repo_type="dataset")
            shutil.copyfile(cached, dest)

    print(f"\nDone! Saved {len(selected_ai)} AI and {len(selected_real)} real images in {args.out}")
    print(f"Run comparison with:\n  python scripts/compare_detectors.py --images {args.out}")


if __name__ == "__main__":
    main()
