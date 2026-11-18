# Backend

FastAPI service that runs the three checks. Setup is in the [main README](../README.md#1-backend).

| Command (from `backend/`) | What it does |
|---|---|
| `uvicorn app.main:app --reload` | Runs the API on http://localhost:8000 (docs at `/docs`) |
| `pytest` | Runs the tests |
| `ruff check .` / `ruff format .` | Lint / format |
| `python -m app.ai.rag.ingest` | Loads the law texts into the vector database |
| `RAG_TEST_DATABASE_URL=<url> pytest tests/test_retrieval.py` | Also checks the search against a real, ingested database |

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
| `REDIS_URL` | | Redis for the job queue |
| `LLM_API_KEY` | | Anthropic API key for the legal report (`AI_MODE=real`) |
| `LLM_MODEL` | `claude-opus-5-5` | Claude model that writes the legal report summary |
