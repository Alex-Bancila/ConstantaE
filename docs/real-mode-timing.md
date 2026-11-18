# Real AI mode: response time

How long `POST /analyze` takes with `AI_MODE=real`, and whether the demo needs
`ASYNC=true` (issue #15).

## How to measure

From `backend/`, with `requirements-vision.txt` installed, the laws ingested
(`python -m app.ai.rag.ingest`) and `LLM_API_KEY` set in `.env`:

```bash
python scripts/measure_analysis.py legitimate-shop --runs 3
python scripts/measure_analysis.py suspicious-seller --runs 3
```

The script starts a local HTTP server for `qa/pages/` automatically (pass `--base` to
use an external server), runs the analysis once **cold** (the vision model and the
embedding model still have to load) and then `--runs` times **warm**. Every run starts
with an empty image cache, so these are the times for a page nobody analysed before.
A page that was already analysed skips the image detection completely (image cache,
7 days).

The backend also logs one line per analysis, e.g.

```
INFO:     app.services.analysis: analysis 3f2c… (real, 3 images): trust=1ms images=1400ms legal=4210ms total=4220ms
```

The images and the legal report run in parallel, so `total` is close to the slower
of the two, not their sum.

## Results

Machine: AMD Ryzen (AMD64 Family 25 Model 117 Stepping 2, 16 logical cores), Windows,
`torch 2.15.0+cpu`, `haywoodsloan/ai-image-detector-deploy` + `intfloat/multilingual-e5-small`.

| Page | Images | Cold images (load + score) | Cold embedding load | Warm images (median) | Warm query embeddings |
|---|---|---|---|---|---|
| `legitimate-shop` | 3 | 10.70 s | 16.22 s | **1.40 s** (1.32–1.53 s) | ~35 ms (2 questions) |
| `suspicious-seller` | 1 | 9.58 s | 14.70 s | **0.41 s** (0.39–0.44 s) | ~103 ms (6 questions) |

Component breakdown:

- **Trust checks:** < 1 ms (rule-based).
- **Vision detector (`haywoodsloan/ai-image-detector-deploy`):** ~9.5–10.7 s cold load
  from local Hugging Face cache; **~0.41–0.47 s per image** warm on CPU (consistent with
  [ai-detector-evaluation.md](ai-detector-evaluation.md)). Downloading an external image
  times out after 10 s.
- **RAG retrieval (`intfloat/multilingual-e5-small` + pgvector):** ~14.7–16.2 s cold
  model load ( ~28 s on first-ever download from Hugging Face); **~17 ms per question**
  warm on CPU (**103 ms** for all 6 questions when every trust check fails) plus a few
  milliseconds for the local Postgres hybrid query.
- **Claude summary (`claude-sonnet-4-6`, ≤ 120 words, `effort="medium"`):** typically
  **~3–6 s** over the network (60 s timeout). Because the legal report and image
  detection run in parallel, warm total time on a 1–3 image demo page is
  `max(images, legal)` ≈ **3–6 s** (or **1.4 s** when only local models run).

## Decision

| Warm total | Cold total | Demo setting |
|---|---|---|
| ≤ 8 s | ≤ 60 s | `ASYNC=false`: one process fewer, nothing to poll |
| > 8 s | ≤ 60 s | `ASYNC=true`: the popup shows progress and polls for up to 60 s |
| any | > 60 s | Also analyse one page right after starting the backend, so the models are loaded before the demo |

**Chosen for the demo:** **`ASYNC=false`** (with one warm-up request right after
starting the backend so the vision and embedding models are already loaded in memory).
Once warm, a 3-image page scores its images in **1.40 s** in parallel with the legal
report, keeping the total response within the 8 s synchronous budget without needing a
separate Redis RQ worker process. If we test live marketplace listings with many (> 10)
uncached high-resolution photos, switch `ASYNC=true`.

## What happens when a part fails

Each part of the analysis fails on its own; the response is still `status: "done"`:

| Part | When it fails (examples) | What the user gets |
|---|---|---|
| One image | Download timeout or 404, not an image (SVG), model crash | That image gets `aiProbability: 0` and a signal saying why; the other images are scored normally. The failure is not cached, so the next analysis tries again |
| Seller trust | A bug in a check | `trust: null`; the legal report still explains the right of withdrawal |
| Legal report: search | Postgres down, laws not ingested, embedding model fails to load | `legal: null` (the popup says there is no legal report) |
| Legal report: LLM | Claude API down, no `LLM_API_KEY` | The retrieved articles, with a note that the summary could not be written |

> A failed image currently shows as "AI 0%" in the popup and badge. Showing it as
> "not analysed" instead is an extension/contract change, left for Filip.
