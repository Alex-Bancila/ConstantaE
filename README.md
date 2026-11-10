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

DevOps (Docker, CI/CD) is not set up yet; Alex will add it.

## Getting started

You need **Python 3.12+**, **Node.js 22+** and **Chrome**.

> **Windows:** clone into a short path such as `C:\dev\ConstantaE`. Some npm packages
> have very deep folders, and `npm install` fails when a path goes over 260 characters.

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
