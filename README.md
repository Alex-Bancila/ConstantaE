# ConstantaE

A browser extension that helps people shop online safely. When you open a product
page, it checks three things:

1. **AI-generated images:** how likely each product photo is to be AI-generated.
2. **Seller trust:** whether the seller shows the details Romanian law requires
   (company registration number, ANPC and SOL links, return policy).
3. **Your rights:** a short legal report based on Romanian consumer law
   (OUG 34/2014, OG 21/1992), with the articles cited. Built with RAG.

## How it works

```
 Shop page                     Extension                          Backend (FastAPI)
┌───────────┐  page data   ┌──────────────┐   POST /analyze   ┌──────────────────────┐
│  content  │ ───────────► │    popup     │ ────────────────► │ trust checks         │
│  script   │ ◄─────────── │  background  │ ◄──────────────── │ AI image detection   │
└───────────┘    badges    └──────────────┘   all 3 results   │ RAG legal report     │
                                                              └──────────────────────┘
```

1. The **content script** reads the product page (images, price, seller, legal links).
2. The **popup** sends that to the **background worker**, which calls the backend.
3. The **backend** runs the three checks and returns one response
   ([API contract](docs/api-contract.md)).
4. The popup shows the results and the content script draws "AI x%" badges on the photos.

## Repository layout

| Folder | What's inside | Owner |
|---|---|---|
| [`extension/`](extension) | Browser extension (WXT, React, TypeScript, Tailwind) | Filip, Ștefana |
| [`backend/app/api`](backend/app/api), [`backend/app/services`](backend/app/services) | HTTP routes, trust checks, putting the results together | David |
| [`backend/app/workers`](backend/app/workers) | Job queue for slow AI work | Marius |
| [`backend/app/ai/rag`](backend/app/ai/rag) | Law ingestion, vector search, legal report | Lucas |
| [`backend/app/ai/vision`](backend/app/ai/vision) | AI-generated image detection | Rareș |
| [`qa/`](qa) | Test pages, labeled images, end-to-end tests | Ovidiu |
| [`shared/`](shared) | Example request and mock response, used by both sides | everyone |
| [`docs/`](docs) | API contract, roadmap | everyone |

Docker Compose runs the backend stack locally (see below). Owner: Alex.

## Getting started

You need **Python 3.12+**, **Node.js 22+** and **Chrome**.

> **Windows:** clone into a short path such as `C:\dev\ConstantaE`. Some npm packages
> have very deep folders, and `npm install` fails when a path goes over 260 characters.

### Quick start with Docker (recommended)

Needs [Docker Desktop](https://www.docker.com/products/docker-desktop/). Starts Postgres
(pgvector), Redis, the API and the worker:

```bash
cp backend/.env.example backend/.env   # Windows: copy backend\.env.example backend\.env
docker compose up --build
```

The first build takes a few minutes (it installs PyTorch).

| Service | From your PC |
|---|---|
| API | http://localhost:8000 (docs at `/docs`) |
| Postgres (pgvector) | `localhost:5440`, user and password `postgres`, database `constantae` |
| Redis | `localhost:6379` |

Inside Docker the services reach each other as `db` and `redis`; `docker-compose.yml`
sets `DATABASE_URL` and `REDIS_URL` for you, so you don't need to change them in `.env`.

Load the law texts into the database (needed for `AI_MODE=real`):

```bash
docker compose exec api python -m app.ai.rag.ingest
```

Stop everything with `docker compose down`. Add `-v` to also delete the database data.
After changing `requirements*.txt` or the `Dockerfile`, rebuild with `docker compose up --build`.

Then load the extension as in step 2 below. The manual backend setup in step 1 is only
needed if you don't use Docker.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs to see and try the API.

### 2. Extension

```bash
cd extension
npm install
copy .env.example .env            # macOS/Linux: cp .env.example .env
npm run dev
```

`npm run dev` opens Chrome with the extension already loaded and reloads it when you
save. To load it into your own Chrome instead: `npm run build`, open
`chrome://extensions`, turn on Developer mode, click **Load unpacked** and pick
`extension/.output/chrome-mv3`.

### 3. Try it

Serve the sample product page and open it:

```bash
python -m http.server 8001 --directory qa/pages/sample
```

Go to http://localhost:8001/product.html and click the extension icon. You should
see the three result sections and an "AI x%" badge on each photo.

## How to run the demo

The demo runs the real AI (`AI_MODE=real`) on the offline pages in `qa/pages`. Setup is
once; the steps after it are what you do every time.

**Once**

1. `docker compose up -d db redis` (Postgres and Redis).
2. In `backend/`: `pip install -r requirements-dev.txt -r requirements-vision.txt`.
3. In `backend/.env`: `AI_MODE=real`, `DATABASE_URL=postgresql://postgres:postgres@localhost:5440/constantae`
   (the port is 5440, not the 5432 in `.env.example`), and your `LLM_API_KEY`. Without
   the key the legal report still lists the articles but has no written summary.
4. Load the laws: `python -m app.ai.rag.ingest` (in `backend/`).
5. In `extension/`: `npm ci`, then `npm run build`, and load `extension/.output/chrome-mv3`
   in Chrome (`chrome://extensions`, Developer mode, Load unpacked).

**Every time**

1. Start the backend on your PC (not in Docker: the container can't reach `localhost:8001`):
   `uvicorn app.main:app` in `backend/`.
2. Serve the pages: `python -m http.server 8001 --directory qa/pages`.
3. Warm up the models with one request, for example
   `node qa/e2e/flow.mjs legitimate-shop`. The first analysis takes about 20 s; later
   ones take a few seconds ([timings](docs/real-mode-timing.md)). Keep `ASYNC=false`.
4. Open `http://localhost:8001/<page>/product.html` for `legitimate-shop`, `ai-photos`,
   `suspicious-seller` or `marketplace-individual`, and click the extension icon.
   Expected results per page are in [qa/pages/README.md](qa/pages/README.md).

To check all pages without a browser, run `node qa/e2e/flow.mjs`. It prints what each page
returns and compares it with the page's `expected.json` (exit code 1 if anything differs).
`http://localhost` fails the HTTPS check, so the HTTPS check fails on every page and its trust score is lower than the
one in `expected.json`.
## Mock mode

Nobody has to wait for anyone else:

- **Backend:** `AI_MODE=mock` (the default) returns fake AI results, so the API works
  before the real models exist.
- **Extension:** `WXT_USE_MOCK=true` returns [`shared/mock-analysis.json`](shared/mock-analysis.json)
  without calling the backend at all.

Search the code for `TODO(<your name>)` to find where your work starts, and see
[docs/roadmap.md](docs/roadmap.md) for each person's tasks.

## Team

| Person | Role |
|---|---|
| Lucas | AI & RAG Pipeline Engineer |
| Rareș | AI Vision & Content Detection Engineer |
| David | Backend Developer (API & Core Logic) |
| Marius | Backend Developer (Async Workers & Storage) |
| Filip | Extension Frontend Developer |
| Ștefana | Extension Content Script Engineer |
| Ovidiu | QA & Testing Engineer |
| Alex | DevOps Engineer |

Before you open your first pull request, read [CONTRIBUTING.md](CONTRIBUTING.md).

*ConstantaE does not give legal advice.*
