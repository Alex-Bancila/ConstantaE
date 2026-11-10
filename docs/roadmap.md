# Roadmap to the demo

The starter project already works end to end with fake AI results: the extension
reads a page, the backend runs the checks and the popup shows them. Each task below
replaces a fake or missing piece with the real one. Search for `TODO(<your name>)`.

**Demo goal:** on 1-2 real sites, open a product page, click the extension and get
AI scores on the photos, the seller trust check and a cited legal report.
User accounts are left out on purpose: they bring the least value to the user right now.

## Lucas: AI & RAG
- [ ] Save the consolidated texts of OUG 34/2014 and OG 21/1992 in `backend/data/laws/`
- [ ] Split them into one chunk per article, with law name, article number and link
- [ ] Create embeddings (BGE-M3 or multilingual-e5) and store them in Postgres + pgvector
- [ ] `retrieve(query, k)` with hybrid search (full-text + vector)
- [ ] `generate_report()`: a question per failed trust check, always the 14-day
      withdrawal right, citing only retrieved articles
- [ ] 10 test questions with the expected article; check each answer cites it

## Rareș: AI Vision
- [ ] Try 2-3 pretrained AI-image detectors from Hugging Face; keep the most accurate
- [ ] `detect(image_url)`: download with a timeout and size limit, return a probability
- [ ] Metadata checks first: C2PA credentials, EXIF "Software", missing camera data
- [ ] Measure accuracy on `qa/images` with Ovidiu; write the number down for the demo
- [ ] Out of scope for the demo: AI text detection

## David: Backend core + integration
- [ ] CUI check-digit validation (and optionally the ANAF public API)
- [ ] Suspicious-price check
- [ ] Database tables for analyses and image results (Postgres)
- [ ] Connect Lucas's and Rareș's real functions and keep the tests green
- [ ] **Integration owner:** run the full flow on the demo pages and fix what doesn't fit

## Marius: Async workers
- [ ] Redis-backed job queue (RQ or Celery) and a worker process
- [ ] `ASYNC=true`: `POST /analyze` returns `pending`, the worker saves the result
- [ ] Move `workers/store.py` from memory to Redis or Postgres
- [ ] Cache image results by a hash of the image URL
- [ ] Keep `ASYNC=false` working as the fallback for the demo

## Filip: Extension UI
- [ ] Polish the popup: loading spinner, empty states, clearer error messages
- [ ] Project logo and icons (replace `extension/public/icon/*`)
- [ ] Show the analysed page's title and price at the top
- [ ] Decide the UI language (Romanian or English) and use it everywhere

## Ștefana: Content script
- [ ] OLX and eMAG selectors where the generic JSON-LD / Open Graph data is missing
- [ ] Seller name and CUI extraction
- [ ] Return policy detection
- [ ] Badges: follow the images on scroll, resize and lazy loading

## Ovidiu: QA + testing
- [ ] 3-5 demo pages saved offline in `qa/pages/`: one legitimate, one with AI images,
      one suspicious
- [ ] Labeled image set in `qa/images/real` and `qa/images/ai` (about 20 each)
- [ ] Extend the backend tests as features land
- [ ] Turn `qa/e2e/smoke.mjs` into a Playwright test suite
- [ ] Dry run of the demo with a checklist; keep the bug list on the board

## Alex: DevOps + video
- [ ] Docker Compose: Postgres (pgvector), Redis, API, worker
- [ ] GitHub Actions CI: backend lint and tests, extension build as a `.zip`
- [ ] Branch protection on `main`: CI green and one approval
- [ ] Demo video: script, slides, recording, editing; send it to the mentor a day early
