# Backend

FastAPI service that runs the three checks. Setup is in the [main README](../README.md#1-backend).

| Command (from `backend/`) | What it does |
|---|---|
| `uvicorn app.main:app --reload` | Runs the API on http://localhost:8000 (docs at `/docs`) |
| `python -m app.workers.worker` | Runs the background worker for async jobs |
| `pytest` | Runs the tests |
| `ruff check .` / `ruff format .` | Lint / format |
| `python -m app.db` | Creates the `analyses` and `image_results` tables (run once) |
| `TEST_DATABASE_URL=<url> pytest tests/test_db.py` | Also checks saving against a real Postgres |
| `python -m app.ai.rag.ingest` | Loads the law texts into the vector database |
| `RAG_TEST_DATABASE_URL=<url> pytest tests/test_retrieval.py` | Also checks the search against a real, ingested database |
| `python -m app.ai.rag.evaluate` | Scores the legal report on the 10 questions in `tests/data/legal_questions.json` (`--retrieval-only` skips the LLM) |
| `python scripts/measure_analysis.py <page>` | Times one analysis of a `qa/pages` demo page with `AI_MODE=real` (see [real-mode-timing.md](../docs/real-mode-timing.md)) |
| `REAL_AI_E2E=1 pytest tests/test_real_e2e.py -s` | Runs `AI_MODE=real` end to end on two demo pages (needs everything in the checklist below) |

## Running with `AI_MODE=real`

The default `AI_MODE=mock` needs none of this. For the real AI:

1. `pip install -r requirements-vision.txt` (PyTorch, for the image detector).
2. Postgres with pgvector (`docker compose up db`) and `DATABASE_URL` in `.env`.
   With Docker Compose from your PC that is `postgresql://postgres:postgres@localhost:5440/constantae`.
3. Load the laws once: `python -m app.ai.rag.ingest`.
4. `LLM_API_KEY` (and optionally `LLM_MODEL`) in `.env`.
5. Redis (`docker compose up redis`): the result store and the image cache use it,
   also with `ASYNC=false`.
6. `AI_MODE=real` in `.env`, then `uvicorn app.main:app`.

The first analysis downloads and loads the models, so it is much slower than the next
ones. Each analysis logs how long its parts took. If one part fails (an image that
can't be downloaded, Postgres down, the LLM unavailable), the error is logged and the
other parts are still returned.

> **Docker and local demo pages:** inside the `api` container, `localhost` is the
> container itself, so it can't download images from `http://localhost:8001/...`.
> For the offline demo pages, run the backend on your PC instead.

## Files

| File | What it does | Owner |
|---|---|---|
| `app/main.py` | Creates the app, CORS for the extension | David |
| `app/api/analyze.py` | `POST /analyze`, `GET /analyze/{id}` | David |
| `app/services/analysis.py` | Runs the three checks and puts the result together | David |
| `app/services/trust.py` | Seller trust checks | David |
| `app/schemas.py` | The API contract (Pydantic models) | everyone |
| `app/config.py` | Settings from `.env` | everyone |
| `app/workers/` | Job queue and result storage | Marius |
| `app/ai/rag/` | Law ingestion, retrieval, legal report | Lucas |
| `app/ai/vision/` | AI-generated image detection | Rareș |
| `data/laws/` | Law texts to ingest | Lucas |

## Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `AI_MODE` | `mock` | `mock` = fake AI results; `real` = run the real AI code |
| `ASYNC` | `false` | `true` = send the AI work to the job queue |
| `DATABASE_URL` | | Postgres with pgvector |
| `REDIS_URL` | `redis://localhost:6379` | Redis for the job queue and result storage |
| `RESULT_TTL_SECONDS` | `86400` | Expiration time for analysis results in Redis (default: 24h) |
| `IMAGE_CACHE_TTL_SECONDS` | `604800` | Expiration time for cached image detection results (default: 7 days) |
| `ANAF_CHECK` | `true` | Confirm the seller's CUI with ANAF's public API. If ANAF is slow or down, the check is skipped |
| `ANAF_TIMEOUT_SECONDS` | `3` | How long to wait for ANAF |
| `ANAF_CACHE_TTL_SECONDS` | `86400` | How long a looked-up company stays cached (default: 1 day) |
| `LLM_API_KEY` | | Anthropic API key for the legal report (`AI_MODE=real`) |
| `LLM_MODEL` | `claude-sonnet-4-6` | Claude model that writes the legal report summary |

### Redis & Worker

To run background jobs, ensure Redis is running:

```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

Start the worker:

```bash
python -m app.workers.worker
```

You can test the queue and worker end-to-end at any time with:

```bash
python -m app.workers.worker --test
```


## Storing analyses in Postgres

Set `DATABASE_URL` and run `python -m app.db` once (with Docker: `docker compose exec api python -m app.db`). It is safe to run again. Every finished analysis is then saved in two tables: `analyses` (page URL and title, status, trust score, trust checks and legal report as JSON) and `image_results` (one row per image, deleted together with its analysis).

Redis (`app/workers/store.py`) stays the store the API reads from: it holds pending, failed and finished results and expires them. Postgres is the permanent history, written by `analysis.run` and not read by the API yet. Without `DATABASE_URL` nothing is saved, and a database error is logged without failing the analysis.

## Suspicious price check

The `suspicious_price` trust check compares the price with the typical price in `data/reference_prices.json` (RON, hand-maintained). A title that matches a listed product and a price under 50% of the typical one fails the check. Products not in the list, accessories, used goods and non-RON prices are skipped. To cover a new product, add an entry with its keywords and price.
