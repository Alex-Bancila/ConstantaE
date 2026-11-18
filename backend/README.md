# Backend

FastAPI service that runs the three checks. Setup is in the [main README](../README.md#1-backend).

| Command (from `backend/`) | What it does |
|---|---|
| `uvicorn app.main:app --reload` | Runs the API on http://localhost:8000 (docs at `/docs`) |
| `python -m app.workers.worker` | Runs the background worker for async jobs |
| `pytest` | Runs the tests |
| `ruff check .` / `ruff format .` | Lint / format |
| `python -m app.ai.rag.ingest` | Loads the law texts into the vector database |
| `RAG_TEST_DATABASE_URL=<url> pytest tests/test_retrieval.py` | Also checks the search against a real, ingested database |
| `python -m app.ai.rag.evaluate` | Scores the legal report on the 10 questions in `tests/data/legal_questions.json` (`--retrieval-only` skips the LLM) |

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

