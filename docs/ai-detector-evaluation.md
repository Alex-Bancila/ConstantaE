# AI-Generated Image Detector: Evaluation & Demo Notes

Owner: **Rareș** (`backend/app/ai/vision/detector.py`)  
Chosen model: **`haywoodsloan/ai-image-detector-deploy`** (SwinV2 architecture, **Apache-2.0** license)  
Evaluation script: `python scripts/evaluate_detector.py --per-image` (from `backend/`)

---

## 1. How the Final Detector Works

When `detect(image_url)` runs with `AI_MODE=real`, it executes a two-stage pipeline:

1. **Cheap Metadata Checks (`_inspect_metadata`):**
   - **C2PA Content Credentials:** Scans raw image bytes for embedded C2PA JUMBF / XMP manifest markers (`urn:c2pa:`, `c2pa.claim`, `c2pa.assertions`, `trainedAlgorithmicMedia`, etc.).
   - **EXIF `Software` Tag (`0x0131`) & Image Info:** Checks whether the image software header names a known AI generator (Midjourney, DALL-E, Stable Diffusion, ComfyUI, Adobe Firefly, Flux, Imagen, Ideogram, Recraft, ChatGPT/OpenAI, Gemini, etc.).
   - **Camera EXIF (`Make` `0x010F` / `Model` `0x0110`):** Reports `"Camera EXIF data present (<Make Model>)"` when present, or `"No camera EXIF data"` when absent.
   - **Probability Floor on Proof:** If C2PA credentials or an AI `Software` tag prove AI generation, `aiProbability` is raised to at least **`0.95`** (`max(model_score, 0.95)`).
2. **Pretrained Vision Model (`_score_image`):**
   - Runs `haywoodsloan/ai-image-detector-deploy` (loaded once via `@lru_cache(maxsize=1)`) and appends `"Model score 0.XX (haywoodsloan/ai-image-detector-deploy)"` to `signals`.

---

## 2. Final Numbers on `qa/images` (20 images: 10 AI, 10 real)

Evaluated at threshold `0.5` on CPU (`torch 2.15.0+cpu`, 8 threads):

| Pipeline Mode | Accuracy | Precision | Recall | ms/image | TP / FP / TN / FN |
|---|---:|---:|---:|---:|---|
| **Full detector (metadata + model)** | **85%** | **77%** | **100%** | 505 | 10 / 3 / 7 / 0 |
| Model only (metadata stripped to JPEG q90) | 50% | 50% | 30% | 474 | 3 / 3 / 7 / 7 |

### Per-Image Breakdown on `qa/images` (Full Detector)

| Image | Label | `aiProbability` | Signals |
|---|---|---:|---|
| `ai/car.png` | ai | 0.97 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 0.97 |
| `ai/cat_mug.png` | ai | 0.99 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 0.99 |
| `ai/glasses.png` | ai | 0.98 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 0.98 |
| `ai/gta.png` | ai | 1.00 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 1.00 |
| `ai/lego.jpeg` | ai | 1.00 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 1.00 |
| `ai/perfume.png` | ai | 1.00 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 1.00 |
| `ai/prada.jpeg` | ai | 0.95 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 0.87 |
| `ai/snoopy.png` | ai | 0.96 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 0.96 |
| `ai/stanley.png` | ai | 0.95 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 0.95 |
| `ai/sweater.png` | ai | 0.95 | C2PA content credentials indicate AI generation; No camera EXIF data; Model score 0.35 |
| `real/ceas.png` | real | 0.01 | No camera EXIF data; Model score 0.01 |
| `real/desk.jpg` | real | 0.93 | No camera EXIF data; Model score 0.93 *(false positive — 512×512 thumbnail)* |
| `real/hat.jpg` | real | 0.01 | No camera EXIF data; Model score 0.01 |
| `real/iphone.png` | real | 0.09 | No camera EXIF data; Model score 0.09 |
| `real/logan.png` | real | 0.02 | No camera EXIF data; Model score 0.02 |
| `real/playstation.png` | real | 0.01 | No camera EXIF data; Model score 0.01 |
| `real/shoe_1.jpg` | real | 0.74 | No camera EXIF data; Model score 0.74 *(false positive — 512×512 thumbnail)* |
| `real/shoe_2.jpg` | real | 0.98 | No camera EXIF data; Model score 0.98 *(false positive — 256×256 thumbnail)* |
| `real/shoe_3.jpg` | real | 0.14 | No camera EXIF data; Model score 0.14 |
| `real/ugg.png` | real | 0.00 | No camera EXIF data; Model score 0.00 |

---

## 3. Expanded Benchmark (`qa/images_extra` — 100 images: 50 AI across 11 modern generators, 50 real)

Evaluated on 100 images from `tellif/ai_vs_real_image_semantically_similar` (Flux Pro, Gemini 2.5 Flash Image, Imagen 4, Stable Diffusion 3.5, Ideogram v2, Recraft v3, Hunyuan, Qwen-Image, etc.):

| Pipeline Mode | Accuracy | Precision | Recall | ms/image | TP / FP / TN / FN |
|---|---:|---:|---:|---:|---|
| **Full detector (metadata + model)** | **86%** | **93%** | **78%** | 474 | 39 / 3 / 47 / 11 |
| Model only (metadata stripped to JPEG q90) | 82% | 90% | 72% | 476 | 36 / 4 / 46 / 14 |

---

## 4. Talking Points for the Demo Video

- **Headline numbers to quote:**
  - On our labeled `qa/images` set: **85% accuracy, 77% precision, and 100% recall** (catches all 10 AI product photos, including `ai/sweater.png` where C2PA Content Credentials caught an AI image that the vision model alone scored `0.35`).
  - On the 100-image multi-generator benchmark: **86% accuracy, 93% precision, and 78% recall** across 11 modern AI generators (only 3 false positives out of 50 real photos).
  - Speed: **~480–500 ms per image on CPU** after warm-up (model is loaded once in memory).
- **Why combining metadata + vision matters:**
  - Generators like ChatGPT/DALL-E, Gemini, and Adobe Firefly embed **C2PA Content Credentials** (`urn:c2pa:`). Checking metadata first gives near-instant proof when credentials are intact, while the SwinV2 vision model catches AI images whose metadata was stripped.

---

## 5. Known Weak Spots & Limitations

1. **Small, heavily compressed square thumbnails (`256×256` / `512×512`):**
   - All 3 false positives on `qa/images` (`real/desk.jpg` at `512×512`, `real/shoe_1.jpg` at `512×512`, and `real/shoe_2.jpg` at `256×256`) are low-resolution square JPEGs (6–30 KB). Heavy JPEG block artifacts and downscaling blur natural camera sensor noise, making real thumbnails look synthetic to vision transformers.
2. **Screenshots and re-saved images:**
   - Taking a screenshot of a real photo strips camera EXIF data, introduces OS scaling/subpixel artifacts, and re-compresses the image, which can elevate false-positive scores.
   - Conversely, screenshotting or uploading an AI image to marketplaces (like OLX or eMAG) usually strips C2PA and EXIF headers, forcing detection to rely purely on the pixel model (where recall is ~72–78%).
3. **Aggressive JPEG recompression:**
   - Re-encoding high-resolution PNG AI images to JPEG quality 90 alters high-frequency pixel statistics that SwinV2 relies on when metadata is absent.
4. **Missing camera EXIF on legitimate e-commerce photos:**
   - Almost all real marketplace photos have EXIF stripped by the platform's CDN for privacy and file-size reasons. Therefore, `"No camera EXIF data"` is reported as an informational signal for transparency, **not** as proof of AI generation on its own.
